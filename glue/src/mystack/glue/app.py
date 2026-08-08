"""Glue Data Catalog FastAPI composition root.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from mystack.aws_protocol import (
    AwsJsonRpcEndpoint,
    AwsServiceModel,
    DiagnosticsSettings,
    HistoryFallbackStaticFiles,
    LoadedConfiguration,
    ManagementUiSettings,
    create_diagnostics_router,
    load_configuration,
)
from mystack.aws_protocol.observability import configure_logging, log_event
from mystack.glue.adapters.inbound import GlueAwsAdapter, GlueManagementAdapter
from mystack.glue.adapters.outbound import JsonCatalogRepository, SystemClock
from mystack.glue.application import CatalogApplication
from mystack.glue.application.ports import Clock
from mystack.glue.config import GlueSettings
from mystack.glue.domain.repositories import CatalogRepository

_LOGGER = logging.getLogger(__name__)


def create_app(
    settings: GlueSettings | None = None,
    *,
    configuration: LoadedConfiguration | None = None,
    application: CatalogApplication | None = None,
    repository: CatalogRepository | None = None,
    clock: Clock | None = None,
    diagnostics_settings: DiagnosticsSettings | None = None,
    log_level: str | None = None,
) -> FastAPI:
    loaded = configuration or (load_configuration() if settings is None else None)
    if settings is None:
        if loaded is None:
            raise ValueError("configuration is required when settings are not supplied")
        settings = GlueSettings.from_configuration(loaded)
    if diagnostics_settings is None:
        if loaded is None:
            raise ValueError("diagnostics_settings are required with explicit Glue settings")
        diagnostics_settings = DiagnosticsSettings.from_configuration(loaded)
    if log_level is None and loaded is not None:
        log_level = str(loaded.document.get("logging", {}).get("level", "INFO"))
    ui_settings = (
        ManagementUiSettings.from_configuration(loaded)
        if loaded is not None
        else ManagementUiSettings(2.0, 0.5, 300.0, 1_048_576)
    )

    configure_logging("glue", log_level)
    repository = repository or JsonCatalogRepository(settings.state_file)
    clock = clock or SystemClock()
    if application is None:
        application = CatalogApplication(
            repository=repository,
            clock=clock,
            policy=settings.policy,
        )
    service_model = AwsServiceModel("glue")
    adapter = GlueAwsAdapter(application, settings.policy.default_catalog_id)
    dispatcher = adapter.dispatcher()
    endpoint = AwsJsonRpcEndpoint(
        service_model,
        dispatcher,
        default_region=settings.default_region,
        account_id=settings.policy.default_catalog_id,
    )
    management = GlueManagementAdapter(
        application,
        catalog_id=settings.policy.default_catalog_id,
        api_page_size=settings.policy.api_page_size,
        implemented_operations=dispatcher.operations,
        model_operation_count=len(service_model.operation_names),
        runtime_profile=settings.runtime.name,
        config_fingerprint=settings.config_fingerprint,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_root.mkdir(parents=True, exist_ok=True)
        await application.initialize()
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.started",
            config_source=settings.config_source,
            config_fingerprint=settings.config_fingerprint,
            data_root=str(settings.data_root),
            state_file=str(settings.state_file),
            operation_count=len(dispatcher.operations),
            operations=sorted(dispatcher.operations),
            runtime_profile={
                "name": settings.runtime.name,
                "spark_version": settings.runtime.spark_version,
                "python_version": settings.runtime.python_version,
                "java_version": settings.runtime.java_version,
                "iceberg_version": settings.runtime.iceberg_version,
            },
        )
        yield
        log_event(_LOGGER, logging.INFO, "glue.stopping")

    app = FastAPI(title="Mystack Glue Data Catalog Emulator", version="0.1.0", lifespan=lifespan)
    app.include_router(create_diagnostics_router("glue", diagnostics_settings))
    app.include_router(
        create_diagnostics_router(
            "glue",
            diagnostics_settings,
            prefix="/_mystack/ui/glue/diagnostics",
        )
    )

    @app.get("/_mystack/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "glue",
                "config_fingerprint": settings.config_fingerprint,
                "implemented_operations": sorted(dispatcher.operations),
                "runtime_profile": settings.runtime.name,
            }
        )

    @app.get("/_mystack/management/resources")
    @app.get("/_mystack/ui/glue/resources")
    async def management_resources() -> JSONResponse:
        return JSONResponse(await management.resources())

    @app.get("/_mystack/ui/glue/config")
    async def ui_config() -> JSONResponse:
        return JSONResponse(ui_settings.document())

    @app.post("/", include_in_schema=False)
    async def aws_json_endpoint(request: Request) -> Response:
        return await endpoint(request)

    @app.get("/_mystack/ui")
    @app.get("/_mystack/ui/")
    async def ui_root() -> RedirectResponse:
        return RedirectResponse("/_mystack/ui/glue/", status_code=307)

    ui_directory = Path(__file__).parent / "static" / "ui"
    app.mount(
        "/_mystack/ui/glue",
        HistoryFallbackStaticFiles(directory=ui_directory, html=True, check_dir=False),
        name="glue-ui",
    )

    return app
