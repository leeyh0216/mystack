"""FastAPI composition root and controller boundary.

Custom endpoint behavior follows:
https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from mystack.aws_protocol import (
    DiagnosticsSettings,
    LoadedConfiguration,
    create_diagnostics_router,
    load_configuration,
)
from mystack.aws_protocol.observability import configure_logging, log_event
from mystack.proxy.config import ProxySettings
from mystack.proxy.ports import ManagementBackendUnavailableError, UnknownManagementComponentError
from mystack.proxy.runtime import ProxyRuntime

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
    runtime = ProxyRuntime(resolved_settings, client=client)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        configure_logging("proxy", log_level)
        try:
            await runtime.start()
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
        finally:
            _log(logging.INFO, "proxy.stopping", runtime_state=runtime.state)
            await runtime.aclose()

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

    @app.get("/_mystack/components")
    async def components() -> JSONResponse:
        names = ["proxy", *[route.name for route in resolved_settings.routes]]
        return JSONResponse({"components": names})

    @app.get("/_mystack/console")
    async def console() -> Response:
        return RedirectResponse("/_mystack/ui/emr/", status_code=307)

    @app.get("/console")
    async def short_console() -> Response:
        return RedirectResponse("/_mystack/ui/emr/", status_code=307)

    @app.get("/_mystack/ui")
    async def ui_root() -> Response:
        return RedirectResponse("/_mystack/ui/emr/", status_code=307)

    @app.get("/_mystack/ui/{component}")
    async def component_ui_root(component: str) -> Response:
        return RedirectResponse(f"/_mystack/ui/{component}/", status_code=307)

    @app.api_route(
        "/_mystack/ui/{component}/{relative_path:path}",
        methods=["GET", "HEAD"],
    )
    async def component_ui(request: Request, component: str, relative_path: str) -> Response:
        _log(
            logging.DEBUG,
            "proxy.service_ui.controller.before",
            component=component,
            relative_path=relative_path,
        )
        try:
            return await runtime.service_ui.forward(
                request,
                component=component,
                relative_path=relative_path,
            )
        except UnknownManagementComponentError:
            return JSONResponse({"detail": "Unknown UI component"}, status_code=404)
        except ManagementBackendUnavailableError:
            return JSONResponse({"detail": "Component UI unavailable"}, status_code=502)

    async def forward_management(
        request: Request,
        *,
        component: str,
        backend_path: str,
        capability: str,
    ) -> Response:
        _log(
            logging.DEBUG,
            "proxy.management.controller.before",
            component=component,
            capability=capability,
        )
        try:
            response = await runtime.management.forward(
                component=component,
                backend_path=backend_path,
                capability=capability,
                query_params=request.query_params.multi_items(),
            )
        except UnknownManagementComponentError:
            return JSONResponse({"detail": "Unknown component"}, status_code=404)
        except ManagementBackendUnavailableError:
            return JSONResponse(
                {"detail": "Component management API unavailable"},
                status_code=502,
            )
        _log(
            logging.DEBUG,
            "proxy.management.controller.after",
            component=component,
            capability=capability,
            status_code=response.status_code,
        )
        return Response(
            response.content,
            status_code=response.status_code,
            media_type=response.content_type,
        )

    @app.get("/_mystack/components/{component}/resources")
    async def component_resources(request: Request, component: str) -> Response:
        if component == "proxy":
            return JSONResponse(
                {
                    "schema_version": 1,
                    "service": "proxy",
                    "emulator": {
                        "mode": "extensible AWS request router",
                        "config_fingerprint": resolved_settings.config_fingerprint,
                        "notice": "Unmatched requests are forwarded to the configured fallback.",
                    },
                    "compatibility": {
                        "classification": "ROUTER",
                        "registered_service_count": len(resolved_settings.routes),
                    },
                    "counts": {"routes": len(resolved_settings.routes)},
                    "resources": {
                        "routes": [
                            {
                                "id": route.name,
                                "name": route.name,
                                "backend_url": route.backend_url,
                                "target_prefixes": route.target_prefixes,
                                "signing_names": route.signing_names,
                                "host_prefixes": route.host_prefixes,
                            }
                            for route in resolved_settings.routes
                        ]
                    },
                }
            )
        return await forward_management(
            request,
            component=component,
            backend_path="/_mystack/management/resources",
            capability="resources",
        )

    @app.get("/_mystack/components/{component}/logs")
    async def component_logs(request: Request, component: str) -> Response:
        if component == "proxy":
            return JSONResponse({"detail": "Proxy has no resource process logs"}, status_code=404)
        return await forward_management(
            request,
            component=component,
            backend_path="/_mystack/management/logs",
            capability="logs",
        )

    @app.get("/_mystack/components/{component}/diagnostics/{kind}")
    async def component_diagnostics(
        request: Request,
        component: str,
        kind: str,
    ) -> Response:
        if kind not in {"threads", "tasks"}:
            return JSONResponse({"detail": "Unknown diagnostic kind"}, status_code=404)
        return await forward_management(
            request,
            component=component,
            backend_path=f"/_mystack/diagnostics/{kind}",
            capability=f"diagnostics.{kind}",
        )

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        include_in_schema=False,
    )
    async def forward(request: Request, path: str) -> Response:
        del path
        return await runtime.aws_requests.forward(request)

    return app


def _log(level: int, event: str, **fields: object) -> None:
    log_event(_LOGGER, level, event, **fields)
