"""Glue Data Catalog FastAPI composition root.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from mystack_aws_protocol import (
    AwsJsonRpcEndpoint,
    AwsServiceModel,
    DiagnosticsSettings,
    LoadedConfiguration,
    create_diagnostics_router,
    load_configuration,
)
from mystack_aws_protocol.observability import configure_logging, log_event

from .adapters.inbound import GlueAwsAdapter
from .adapters.outbound import JsonCatalogRepository, SystemClock
from .application import CatalogApplication
from .config import GlueSettings

_LOGGER = logging.getLogger(__name__)


def create_app(
    settings: GlueSettings | None = None,
    *,
    configuration: LoadedConfiguration | None = None,
    application: CatalogApplication | None = None,
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

    application = application or CatalogApplication(
        repository=JsonCatalogRepository(settings.state_file),
        clock=SystemClock(),
        policy=settings.policy,
    )
    adapter = GlueAwsAdapter(application, settings.policy.default_catalog_id)
    dispatcher = adapter.dispatcher()
    endpoint = AwsJsonRpcEndpoint(
        AwsServiceModel("glue"),
        dispatcher,
        default_region=settings.default_region,
        account_id=settings.policy.default_catalog_id,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging("glue", log_level)
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

    @app.post("/", include_in_schema=False)
    async def aws_json_endpoint(request: Request) -> Response:
        return await endpoint(request)

    return app
