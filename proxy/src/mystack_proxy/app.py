"""FastAPI composition root and controller boundary.

Custom endpoint behavior follows:
https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from mystack_aws_protocol import (
    DiagnosticsSettings,
    LoadedConfiguration,
    create_diagnostics_router,
    load_configuration,
)
from mystack_aws_protocol.observability import configure_logging, log_event

from .config import ProxySettings
from .forwarder import AwsRequestForwarder

_LOGGER = logging.getLogger(__name__)


def create_app(
    settings: ProxySettings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    configuration: LoadedConfiguration | None = None,
    diagnostics_settings: DiagnosticsSettings | None = None,
    log_level: str | None = None,
) -> FastAPI:
    loaded = configuration or (load_configuration() if settings is None else None)
    if settings is None:
        if loaded is None:
            raise ValueError("configuration is required when settings are not supplied")
        resolved_settings = ProxySettings.from_configuration(loaded)
    else:
        resolved_settings = settings
    if diagnostics_settings is None:
        if loaded is None:
            raise ValueError("diagnostics_settings are required with explicit proxy settings")
        diagnostics_settings = DiagnosticsSettings.from_configuration(loaded)
    if log_level is None and loaded:
        log_level = str(loaded.document.get("logging", {}).get("level", "INFO"))
    owns_client = client is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging("proxy", log_level)
        resolved_client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(resolved_settings.request_timeout_seconds)
        )
        app.state.forwarder = AwsRequestForwarder(resolved_client, resolved_settings)
        _log(
            logging.INFO,
            "proxy.started",
            config_source=resolved_settings.config_source,
            config_fingerprint=resolved_settings.config_fingerprint,
            fallback_url=resolved_settings.fallback_url,
            routes=[
                {
                    "name": route.name,
                    "backend_url": route.backend_url,
                    "target_prefixes": route.target_prefixes,
                    "signing_names": route.signing_names,
                }
                for route in resolved_settings.routes
            ],
        )
        yield
        _log(logging.INFO, "proxy.stopping")
        if owns_client:
            await resolved_client.aclose()

    app = FastAPI(title="Mystack Proxy", version="0.1.0", lifespan=lifespan)
    app.include_router(create_diagnostics_router("proxy", diagnostics_settings))

    @app.get("/_mystack/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "proxy",
                "config_fingerprint": resolved_settings.config_fingerprint,
            }
        )

    @app.get("/_mystack/routes")
    async def routes() -> JSONResponse:
        return JSONResponse(
            {
                "fallback_url": resolved_settings.fallback_url,
                "routes": [
                    {
                        "name": route.name,
                        "backend_url": route.backend_url,
                        "target_prefixes": route.target_prefixes,
                        "signing_names": route.signing_names,
                        "host_prefixes": route.host_prefixes,
                    }
                    for route in resolved_settings.routes
                ],
            }
        )

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        include_in_schema=False,
    )
    async def forward(request: Request, path: str) -> Response:
        del path
        forwarder: AwsRequestForwarder = request.app.state.forwarder
        return await forwarder.forward(request)

    return app


def _log(level: int, event: str, **fields: object) -> None:
    log_event(_LOGGER, level, event, **fields)
