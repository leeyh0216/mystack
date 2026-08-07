"""Transparent, byte-preserving HTTP forwarding boundary.

Hop-by-hop handling follows RFC 9110 section 7.6.1:
https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.1
"""

from __future__ import annotations

import logging
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

    async def forward(self, request: Request) -> Response:
        started = time.monotonic()
        match = self._detector.detect(request.headers)
        base_url = match.route.backend_url if match.route else self._settings.fallback_url
        target_url = f"{base_url.rstrip('/')}{request.url.path}"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        body = await request.body()
        route_name = match.route.name if match.route else "fallback"
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
