"""Transparent, byte-preserving HTTP forwarding boundary.

Hop-by-hop handling follows RFC 9110 section 7.6.1:
https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.1
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping

import httpx
from fastapi import Request
from fastapi.responses import Response
from mystack_aws_protocol.observability import log_event, payload_fingerprint

from .config import ProxySettings
from .routing import AwsServiceDetector

_LOGGER = logging.getLogger(__name__)

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_CLIENT_VERSION = re.compile(
    r"(?P<name>Boto3|Botocore|aws-cli|aws-sdk-java)[/#](?P<version>[^\s]+)",
    flags=re.IGNORECASE,
)


class AwsRequestForwarder:
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: ProxySettings,
        detector: AwsServiceDetector | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._detector = detector or AwsServiceDetector(settings.routes)

    @property
    def client(self) -> httpx.AsyncClient:
        """Expose the shared pool to composition-root management requests."""

        return self._client

    async def forward(self, request: Request) -> Response:
        started = time.monotonic()
        match = self._detector.detect(request.headers)
        base_url = match.route.backend_url if match.route else self._settings.fallback_url
        target_url = f"{base_url.rstrip('/')}{request.url.path}"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        body = await request.body()
        route_name = match.route.name if match.route else "fallback"
        client_versions = sorted(
            {
                f"{value.group('name').lower()}={value.group('version')}"
                for value in _CLIENT_VERSION.finditer(request.headers.get("user-agent", ""))
            }
        )
        protocol_evidence = {
            "target_prefix": match.target_prefix,
            "signing_name": match.signing_name,
            "host_prefix": match.host_prefix,
            "content_type": request.headers.get("content-type", ""),
            "client_versions": client_versions,
        }
        if match.route is None:
            _log(
                logging.WARNING,
                "proxy.routing.fallback",
                method=request.method,
                path=request.url.path,
                fallback_url=self._settings.fallback_url,
                **protocol_evidence,
                fix_hint=(
                    "If an emulator request unexpectedly reached fallback, compare the current "
                    "SDK service model metadata and add its target/signing/host evidence to "
                    "proxy.routes in the YAML configuration; change routing.py only if the AWS "
                    "evidence format itself changed."
                ),
            )
        _log(
            logging.INFO,
            "proxy.forward.started",
            method=request.method,
            path=request.url.path,
            route=route_name,
            routing_evidence=match.evidence,
            matched_value=match.matched_value,
            backend_origin=base_url,
            payload_bytes=len(body),
            payload_fingerprint=payload_fingerprint(body),
            **protocol_evidence,
        )
        try:
            response = await self._client.request(
                method=request.method,
                url=target_url,
                headers=self._request_headers(request.headers),
                content=body,
            )
        except Exception:
            _log(
                logging.ERROR,
                "proxy.forward.failed",
                route=route_name,
                backend_origin=base_url,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                fix_hint=(
                    "Check the declarative route backend URL and target emulator health; "
                    "the proxy did not receive an HTTP response."
                ),
                exc_info=True,
            )
            raise
        _log(
            logging.INFO,
            "proxy.forward.completed",
            route=route_name,
            backend_origin=base_url,
            status_code=response.status_code,
            response_bytes=len(response.content),
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=self._response_headers(response.headers),
        )

    @staticmethod
    def _request_headers(headers: Mapping[str, str]) -> dict[str, str]:
        return {
            key: value
            for key, value in headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length"}
        }

    @staticmethod
    def _response_headers(headers: Mapping[str, str]) -> dict[str, str]:
        return {
            key: value
            for key, value in headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length", "content-encoding"}
        }


def _log(level: int, event: str, *, exc_info: bool = False, **fields: object) -> None:
    log_event(_LOGGER, level, event, exc_info=exc_info, **fields)
