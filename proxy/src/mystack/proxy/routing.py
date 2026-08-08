"""Extensible service detection from AWS JSON protocol and SigV4 evidence.

References:
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html
- https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .config import ServiceRoute
from .ports import RouteMatch

_CREDENTIAL_SCOPE = re.compile(
    r"Credential=[^/]+/\d{8}/[^/]+/(?P<service>[^/]+)/aws4_request",
    flags=re.IGNORECASE,
)


class AwsServiceDetector:
    def __init__(self, routes: Sequence[ServiceRoute]) -> None:
        self._routes = tuple(routes)

    def detect(self, headers: Mapping[str, str]) -> RouteMatch:
        normalized = {key.lower(): value for key, value in headers.items()}
        target = normalized.get("x-amz-target", "")
        target_prefix = target.partition(".")[0]
        authorization = normalized.get("authorization", "")
        match = _CREDENTIAL_SCOPE.search(authorization)
        signing_name = match.group("service").lower() if match else ""
        host = normalized.get("host", "").split(":", maxsplit=1)[0].lower()
        first_host_label = host.partition(".")[0]

        for route in self._routes:
            if target_prefix in route.target_prefixes:
                return RouteMatch(
                    route,
                    "x-amz-target",
                    target_prefix,
                    target_prefix,
                    signing_name,
                    first_host_label,
                )

        for route in self._routes:
            if signing_name and signing_name in {name.lower() for name in route.signing_names}:
                return RouteMatch(
                    route,
                    "sigv4-credential-scope",
                    signing_name,
                    target_prefix,
                    signing_name,
                    first_host_label,
                )

        for route in self._routes:
            if first_host_label in {prefix.lower() for prefix in route.host_prefixes}:
                return RouteMatch(
                    route,
                    "host-prefix",
                    first_host_label,
                    target_prefix,
                    signing_name,
                    first_host_label,
                )
        return RouteMatch(
            None,
            "fallback",
            first_host_label,
            target_prefix,
            signing_name,
            first_host_label,
        )
