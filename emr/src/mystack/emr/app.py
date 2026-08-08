"""EMR FastAPI composition root.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
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
from mystack.emr.adapters.inbound import (
    EmrAwsAdapter,
    EmrLogEventStream,
    EmrManagementAdapter,
    StartupClusterPlan,
    StartupClusterProvisioner,
    load_startup_cluster_plan,
)
from mystack.emr.adapters.outbound import (
    AsyncioTaskScheduler,
    InMemoryClusterRepository,
    LocalBootstrapRunner,
    LocalProcessExecutor,
    LocalSparkStepRunner,
    RandomAwsIds,
    S3ArtifactStore,
    S3StepLogPublisher,
    StepExecutionJournal,
    SystemClock,
)
from mystack.emr.application import EmrApplication
from mystack.emr.config import EmrSettings
from mystack.emr.domain.errors import EmrDomainError
from mystack.emr.runtime import EmrRuntime

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
    ui_settings = (
        ManagementUiSettings.from_configuration(loaded)
        if loaded is not None
        else ManagementUiSettings(2.0, 0.5, 300.0, 1_048_576)
    )

    owned_runtime: EmrRuntime | None = None
    journal: StepExecutionJournal | None = None
    startup_plan = StartupClusterPlan.disabled()
    if application is None:
        startup_plan = load_startup_cluster_plan(settings.startup_clusters_file, settings.policy)
        repository = InMemoryClusterRepository()
        executor = LocalProcessExecutor(settings)
        artifacts = S3ArtifactStore(settings.object_store)
        logs = S3StepLogPublisher(settings.object_store, settings.log_delivery)
        journal = StepExecutionJournal(settings.work_root, logs, settings.log_delivery)
        application = EmrApplication(
            repository=repository,
            clock=SystemClock(),
            ids=RandomAwsIds(),
            bootstrap_runner=LocalBootstrapRunner(settings, artifacts, executor),
            step_runner=LocalSparkStepRunner(settings, artifacts, executor, journal),
            scheduler=AsyncioTaskScheduler(settings.shutdown_timeout_seconds),
            policy=settings.policy,
        )
        startup = StartupClusterProvisioner(
            application,
            startup_plan,
            region=settings.object_store.region,
            account_id=settings.account_id,
        )
        owned_runtime = EmrRuntime.build(
            application,
            executor,
            artifacts,
            logs,
            journal,
            startup,
            settings,
        )
        application = owned_runtime.application
    adapter = EmrAwsAdapter(application, application, application)
    dispatcher = adapter.dispatcher()
    service_model = AwsServiceModel("emr")
    endpoint = AwsJsonRpcEndpoint(
        service_model,
        dispatcher,
        default_region=settings.object_store.region,
        account_id=settings.account_id,
    )
    management = EmrManagementAdapter(
        application,
        work_root=settings.work_root,
        output_tail_bytes=settings.output_tail_bytes,
        live_chunk_bytes=settings.log_delivery.live_chunk_bytes,
        implemented_operations=dispatcher.operations,
        model_operation_count=len(service_model.operation_names),
        config_fingerprint=settings.config_fingerprint,
        default_release_label=settings.policy.default_release_label,
        release_profiles={
            label: {
                "runtime_profile": profile.runtime_profile,
                "aws_spark_version": profile.aws_spark_version,
                "submit_aliases": list(settings.runtimes[profile.runtime_profile].submit_aliases),
            }
            for label, profile in settings.policy.release_profiles.items()
        },
        startup_cluster_source=startup_plan.source,
        startup_cluster_fingerprint=startup_plan.fingerprint,
        startup_cluster_count=len(startup_plan.commands),
        execution_journal=journal,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        configure_logging("emr", log_level)
        try:
            if owned_runtime is not None:
                await owned_runtime.start()
            else:
                settings.work_root.mkdir(parents=True, exist_ok=True)
                await application.start()
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.started",
                config_source=settings.config_source,
                config_fingerprint=settings.config_fingerprint,
                work_root=str(settings.work_root),
                operation_count=len(dispatcher.operations),
                operations=sorted(dispatcher.operations),
                startup_cluster_source=startup_plan.source,
                startup_cluster_fingerprint=startup_plan.fingerprint,
                startup_cluster_count=len(startup_plan.commands),
                release_profiles={
                    key: {
                        "runtime_profile": value.runtime_profile,
                        "aws_spark_version": value.aws_spark_version,
                    }
                    for key, value in settings.policy.release_profiles.items()
                },
            )
            yield
        finally:
            log_event(_LOGGER, logging.INFO, "emr.stopping")
            if owned_runtime is not None:
                await owned_runtime.close()
            else:
                await application.close()

    app = FastAPI(title="Mystack EMR Emulator", version="0.1.0", lifespan=lifespan)
    app.include_router(create_diagnostics_router("emr", diagnostics_settings))
    app.include_router(
        create_diagnostics_router(
            "emr",
            diagnostics_settings,
            prefix="/_mystack/ui/emr/diagnostics",
        )
    )
    log_stream = EmrLogEventStream(management, ui_settings)

    @app.get("/_mystack/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "emr",
                "config_fingerprint": settings.config_fingerprint,
                "startup_clusters": {
                    "source": startup_plan.source,
                    "fingerprint": startup_plan.fingerprint,
                    "configured_count": len(startup_plan.commands),
                },
                "implemented_operations": sorted(dispatcher.operations),
            }
        )

    @app.get("/_mystack/management/resources")
    @app.get("/_mystack/ui/emr/resources")
    async def management_resources() -> JSONResponse:
        return JSONResponse(await management.resources())

    @app.get("/_mystack/management/logs")
    @app.get("/_mystack/ui/emr/logs")
    async def management_logs(
        cluster_id: str,
        step_id: str,
    ) -> JSONResponse:
        try:
            return JSONResponse(await management.logs(cluster_id, step_id))
        except EmrDomainError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/_mystack/management/logs/chunk")
    @app.get("/_mystack/ui/emr/logs/chunk")
    async def management_log_chunk(
        cluster_id: str,
        step_id: str,
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> JSONResponse:
        try:
            return JSONResponse(
                await management.log_chunk(
                    cluster_id,
                    step_id,
                    stdout_offset=stdout_offset,
                    stderr_offset=stderr_offset,
                )
            )
        except EmrDomainError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/_mystack/ui/emr/config")
    async def ui_config() -> JSONResponse:
        return JSONResponse(ui_settings.document())

    @app.get("/_mystack/ui/emr/log-stream")
    async def ui_log_stream(
        request: Request,
        cluster_id: str,
        step_id: str,
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> Response:
        if stdout_offset < 0 or stderr_offset < 0:
            return JSONResponse({"detail": "Log offsets must be non-negative"}, status_code=400)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.ui.log_stream.controller.before",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
        )
        return StreamingResponse(
            log_stream.events(
                request,
                cluster_id=cluster_id,
                step_id=step_id,
                stdout_offset=stdout_offset,
                stderr_offset=stderr_offset,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    @app.post("/", include_in_schema=False)
    async def aws_json_endpoint(request: Request) -> Response:
        return await endpoint(request)

    @app.get("/_mystack/ui")
    @app.get("/_mystack/ui/")
    async def ui_root() -> RedirectResponse:
        return RedirectResponse("/_mystack/ui/emr/", status_code=307)

    ui_directory = Path(__file__).parent / "static" / "ui"
    app.mount(
        "/_mystack/ui/emr",
        HistoryFallbackStaticFiles(directory=ui_directory, html=True, check_dir=False),
        name="emr-ui",
    )

    return app
