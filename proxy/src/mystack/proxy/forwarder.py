"""Transparent, byte-preserving HTTP forwarding boundary.

Hop-by-hop handling follows RFC 9110 section 7.6.1:
https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.1

HEAD representation metadata follows RFC 9110 section 9.3.2 and S3 HeadObject:
https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.2
https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html

Raw encoded response iteration follows the HTTPX async streaming contract:
https://www.python-httpx.org/async/#streaming-responses
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping, Sequence
from urllib.parse import quote

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from mystack.aws_protocol.observability import log_event, payload_fingerprint
from mystack.proxy.config import ProxySettings, ServiceRoute
from mystack.proxy.ports import (
    ManagementBackendUnavailableError,
    ManagementResponse,
    RouteDetector,
    UnknownManagementComponentError,
)

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
        detector: RouteDetector,
    ) -> None:
        self._client = client
        self._settings = settings
        self._detector = detector

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
        response: httpx.Response | None = None
        try:
            upstream_request = self._client.build_request(
                method=request.method,
                url=target_url,
                headers=self._request_headers(request.headers),
                content=body,
            )
            response = await self._client.send(upstream_request, stream=True)
            response_content_encoding = response.headers.get("content-encoding", "")
            response_body_decoded = (
                request.method != "HEAD"
                and response.is_stream_consumed
                and bool(response_content_encoding)
            )
            response_content = (
                response.content
                if response.is_stream_consumed
                else b"".join([chunk async for chunk in response.aiter_raw()])
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
        finally:
            if response is not None:
                await response.aclose()
        _log(
            logging.INFO,
            "proxy.forward.completed",
            route=route_name,
            backend_origin=base_url,
            status_code=response.status_code,
            response_bytes=len(response_content),
            response_content_encoding=response_content_encoding,
            response_body_decoded=response_body_decoded,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return Response(
            content=response_content,
            status_code=response.status_code,
            headers=self._response_headers(
                response.headers,
                preserve_representation_headers=request.method == "HEAD",
                body_decoded=response_body_decoded,
            ),
        )

    @staticmethod
    def _request_headers(headers: Mapping[str, str]) -> dict[str, str]:
        return {
            key: value
            for key, value in headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length"}
        }

    @staticmethod
    def _response_headers(
        headers: Mapping[str, str],
        *,
        preserve_representation_headers: bool,
        body_decoded: bool,
    ) -> dict[str, str]:
        removed = set(_HOP_BY_HOP_HEADERS)
        if not preserve_representation_headers:
            # The raw encoded body is preserved. Starlette recalculates only its wire length;
            # content encoding and AWS checksum headers must continue to describe these bytes.
            removed.add("content-length")
        if body_decoded:
            removed.add("content-encoding")
        return {
            key: value
            for key, value in headers.items()
            if key.lower() not in removed
            and not (body_decoded and key.lower().startswith("x-amz-checksum-"))
        }


class HttpManagementForwarder:
    """Forward management reads without exposing the shared HTTP client."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        routes: Sequence[ServiceRoute],
    ) -> None:
        self._client = client
        self._routes = {route.name: route for route in routes}

    async def forward(
        self,
        *,
        component: str,
        backend_path: str,
        capability: str,
        query_params: Sequence[tuple[str, str]],
    ) -> ManagementResponse:
        route = self._routes.get(component)
        if route is None:
            raise UnknownManagementComponentError(component)
        started = time.monotonic()
        _log(
            logging.INFO,
            "proxy.management.forward.before",
            component=component,
            capability=capability,
            backend_url=route.backend_url,
            side_effect=True,
        )
        try:
            response = await self._client.get(
                f"{route.backend_url}{backend_path}",
                params=query_params,
            )
        except httpx.HTTPError as error:
            _log(
                logging.ERROR,
                "proxy.management.forward.failed",
                component=component,
                capability=capability,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                fix_hint="Check the component health and proxy route backend_url.",
                side_effect=True,
                exc_info=True,
            )
            raise ManagementBackendUnavailableError(component) from error
        _log(
            logging.INFO,
            "proxy.management.forward.after",
            component=component,
            capability=capability,
            status_code=response.status_code,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
            side_effect=True,
        )
        return ManagementResponse(
            content=response.content,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", "application/json"),
        )


class HttpServiceUiForwarder:
    """Stream service-owned UI assets and APIs through stable Proxy paths."""

    def __init__(self, client: httpx.AsyncClient, routes: Sequence[ServiceRoute]) -> None:
        self._client = client
        self._routes = {route.name: route for route in routes}

    async def forward(
        self,
        request: Request,
        *,
        component: str,
        relative_path: str,
    ) -> Response:
        route = self._routes.get(component)
        if route is None:
            raise UnknownManagementComponentError(component)
        if any(part in {".", ".."} for part in relative_path.split("/")):
            return Response(status_code=404)
        encoded_path = quote(relative_path, safe="/-._~")
        target_url = (
            f"{route.backend_url.rstrip('/')}/_mystack/ui/{quote(component, safe='-._~')}/"
            f"{encoded_path}"
        )
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"
        started = time.monotonic()
        _log(
            logging.INFO,
            "proxy.service_ui.forward.before",
            component=component,
            relative_path=relative_path,
            backend_url=route.backend_url,
            side_effect=False,
        )
        try:
            upstream_request = self._client.build_request(
                request.method,
                target_url,
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower()
                    not in _HOP_BY_HOP_HEADERS
                    | {"authorization", "content-length", "cookie", "host"}
                },
            )
            response = await self._client.send(upstream_request, stream=True)
        except httpx.HTTPError as error:
            _log(
                logging.ERROR,
                "proxy.service_ui.forward.failed",
                component=component,
                relative_path=relative_path,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                fix_hint="Check the configured service backend and its /_mystack/ui health.",
                side_effect=False,
                exc_info=True,
            )
            raise ManagementBackendUnavailableError(component) from error

        async def body():
            response_bytes = 0
            try:
                if response.is_stream_consumed:
                    response_bytes = len(response.content)
                    yield response.content
                else:
                    async for chunk in response.aiter_raw():
                        response_bytes += len(chunk)
                        yield chunk
            finally:
                await response.aclose()
                _log(
                    logging.INFO,
                    "proxy.service_ui.forward.after",
                    component=component,
                    relative_path=relative_path,
                    status_code=response.status_code,
                    response_bytes=response_bytes,
                    duration_ms=round((time.monotonic() - started) * 1000, 3),
                    side_effect=False,
                )

        return StreamingResponse(
            body(),
            status_code=response.status_code,
            headers={
                key: value
                for key, value in response.headers.items()
                if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length"}
            },
        )


def _log(level: int, event: str, *, exc_info: bool = False, **fields: object) -> None:
    log_event(_LOGGER, level, event, exc_info=exc_info, **fields)
