"""EMR FastAPI composition root.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
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

from .adapters.inbound import EmrAwsAdapter
from .adapters.outbound import (
    AsyncioTaskScheduler,
    InMemoryClusterRepository,
    LocalBootstrapRunner,
    LocalProcessExecutor,
    LocalSparkStepRunner,
    RandomAwsIds,
    S3ArtifactStore,
    SystemClock,
)
from .application import EmrApplication
from .config import EmrSettings

_LOGGER = logging.getLogger(__name__)


def create_app(
    settings: EmrSettings | None = None,
    *,
    configuration: LoadedConfiguration | None = None,
    application: EmrApplication | None = None,
    diagnostics_settings: DiagnosticsSettings | None = None,
    log_level: str | None = None,
) -> FastAPI:
    loaded = configuration or (load_configuration() if settings is None else None)
    if settings is None:
        if loaded is None:
            raise ValueError("configuration is required when settings are not supplied")
        settings = EmrSettings.from_configuration(loaded)
    if diagnostics_settings is None:
        if loaded is None:
            raise ValueError("diagnostics_settings are required with explicit EMR settings")
        diagnostics_settings = DiagnosticsSettings.from_configuration(loaded)
    if log_level is None and loaded is not None:
        log_level = str(loaded.document.get("logging", {}).get("level", "INFO"))

    if application is None:
        repository = InMemoryClusterRepository()
        executor = LocalProcessExecutor(settings)
        artifacts = S3ArtifactStore(settings.object_store)
        application = EmrApplication(
            repository=repository,
            clock=SystemClock(),
            ids=RandomAwsIds(),
            bootstrap_runner=LocalBootstrapRunner(settings, artifacts, executor),
            step_runner=LocalSparkStepRunner(settings, artifacts, executor),
            scheduler=AsyncioTaskScheduler(),
            policy=settings.policy,
        )
    adapter = EmrAwsAdapter(application)
    dispatcher = adapter.dispatcher()
    endpoint = AwsJsonRpcEndpoint(
        AwsServiceModel("emr"),
        dispatcher,
        default_region=settings.object_store.region,
        account_id=settings.account_id,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging("emr", log_level)
        settings.work_root.mkdir(parents=True, exist_ok=True)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.started",
            config_source=settings.config_source,
            config_fingerprint=settings.config_fingerprint,
            work_root=str(settings.work_root),
            operation_count=len(dispatcher.operations),
            operations=sorted(dispatcher.operations),
            release_profiles={
                key: {
                    "runtime_profile": value.runtime_profile,
                    "aws_spark_version": value.aws_spark_version,
                }
                for key, value in settings.policy.release_profiles.items()
            },
        )
        yield
        log_event(_LOGGER, logging.INFO, "emr.stopping")

    app = FastAPI(title="Mystack EMR Emulator", version="0.1.0", lifespan=lifespan)
    app.include_router(create_diagnostics_router("emr", diagnostics_settings))

    @app.get("/_mystack/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "emr",
                "config_fingerprint": settings.config_fingerprint,
                "implemented_operations": sorted(dispatcher.operations),
            }
        )

    @app.post("/", include_in_schema=False)
    async def aws_json_endpoint(request: Request) -> Response:
        return await endpoint(request)

    return app
