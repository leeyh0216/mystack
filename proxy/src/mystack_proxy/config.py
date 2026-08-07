"""Proxy settings mapped from the versioned Mystack YAML document.

References:
- https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
- https://docs.docker.com/reference/compose-file/configs/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mystack_aws_protocol.configuration import (
    ConfigurationError,
    LoadedConfiguration,
    require_mapping,
)


@dataclass(frozen=True, slots=True)
class ServiceRoute:
    name: str
    backend_url: str
    target_prefixes: tuple[str, ...]
    signing_names: tuple[str, ...]
    host_prefixes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, document: dict[str, Any]) -> ServiceRoute:
        try:
            return cls(
                name=str(document["name"]),
                backend_url=str(document["backend_url"]),
                target_prefixes=tuple(map(str, document.get("target_prefixes", ()))),
                signing_names=tuple(map(str, document.get("signing_names", ()))),
                host_prefixes=tuple(map(str, document.get("host_prefixes", ()))),
            )
        except KeyError as error:
            raise ConfigurationError(
                f"Proxy route is missing required key: {error.args[0]}"
            ) from error


@dataclass(frozen=True, slots=True)
class ProxySettings:
    fallback_url: str
    routes: tuple[ServiceRoute, ...]
    request_timeout_seconds: float
    listen_host: str
    listen_port: int
    config_source: str
    config_fingerprint: str

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> ProxySettings:
        proxy = require_mapping(loaded.document, "proxy")
        listen = require_mapping(proxy, "listen")
        route_documents = proxy.get("routes")
        if not isinstance(route_documents, list):
            raise ConfigurationError("proxy.routes must be a list")
        routes = tuple(ServiceRoute.from_mapping(route) for route in route_documents)
        _validate_routes(routes)
        try:
            return cls(
                fallback_url=str(proxy["fallback_url"]),
                routes=routes,
                request_timeout_seconds=float(proxy["request_timeout_seconds"]),
                listen_host=str(listen["host"]),
                listen_port=int(listen["port"]),
                config_source=loaded.source,
                config_fingerprint=loaded.fingerprint,
            )
        except KeyError as error:
            raise ConfigurationError(
                f"proxy configuration is missing required key: {error.args[0]}"
            ) from error


def _validate_routes(routes: tuple[ServiceRoute, ...]) -> None:
    names = [route.name for route in routes]
    if len(names) != len(set(names)):
        raise ConfigurationError("proxy route names must be unique")
    for attribute in ("target_prefixes", "signing_names", "host_prefixes"):
        claimed: dict[str, str] = {}
        for route in routes:
            for value in getattr(route, attribute):
                normalized = value.lower()
                previous = claimed.get(normalized)
                if previous:
                    raise ConfigurationError(
                        f"proxy route collision for {attribute} value {value!r}: "
                        f"claimed by {previous!r} and {route.name!r}"
                    )
                claimed[normalized] = route.name
