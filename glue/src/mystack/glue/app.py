"""Glue Data Catalog FastAPI composition root.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from importlib.metadata import version as distribution_version
from pathlib import Path
from urllib.parse import urlparse

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
from mystack.glue.adapters.outbound import (
    S3IcebergMetadataStore,
    SparkTableOptimizerExecutor,
    SparkTableOptimizerExecutorSettings,
    SqliteCatalogRepository,
    SQLiteRuntimeVerification,
    SQLiteRuntimeVerifier,
    SystemClock,
    SystemIdentifierGenerator,
)
from mystack.glue.application import CatalogApplication
from mystack.glue.application.catalog_ports import CatalogStore
from mystack.glue.application.ports import (
    Clock,
    IcebergMetadataStore,
    IdentifierGenerator,
    TableOptimizerExecutor,
)
from mystack.glue.application.table_optimizer_runtime import TableOptimizerRuntime
from mystack.glue.config import GlueSettings

_LOGGER = logging.getLogger(__name__)


def verify_sqlite_runtime(settings: GlueSettings) -> dict[str, object]:
    """Run the configured SQLite preflight without starting the Glue HTTP service."""
    return SQLiteRuntimeVerifier(settings.sqlite).verify().document()


def create_app(
    settings: GlueSettings | None = None,
    *,
    configuration: LoadedConfiguration | None = None,
    application: CatalogApplication | None = None,
    catalog: CatalogStore | None = None,
    clock: Clock | None = None,
    iceberg_metadata_store: IcebergMetadataStore | None = None,
    identifier_generator: IdentifierGenerator | None = None,
    table_optimizer_executor: TableOptimizerExecutor | None = None,
    table_optimizer_runtime: TableOptimizerRuntime | None = None,
    sqlite_runtime_verifier: SQLiteRuntimeVerifier | None = None,
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
    sqlite_runtime_verifier = sqlite_runtime_verifier or SQLiteRuntimeVerifier(settings.sqlite)
    catalog = catalog or SqliteCatalogRepository(settings.sqlite)
    clock = clock or SystemClock()
    owned_metadata_store: S3IcebergMetadataStore | None = None
    object_store_endpoint = urlparse(settings.object_store.endpoint_url)
    if application is None:
        if iceberg_metadata_store is None:
            owned_metadata_store = S3IcebergMetadataStore(settings.object_store)
            iceberg_metadata_store = owned_metadata_store
        application = CatalogApplication(
            read_catalog=catalog,
            query_catalog=catalog,
            write_catalog=catalog,
            clock=clock,
            policy=settings.policy,
            iceberg_metadata_store=iceberg_metadata_store,
            identifier_generator=identifier_generator or SystemIdentifierGenerator(),
            table_optimizer_policy=settings.table_optimizers.policy,
        )
    if table_optimizer_runtime is None and settings.table_optimizers.enabled:
        if table_optimizer_executor is None:
            optimizer = settings.table_optimizers
            table_optimizer_executor = SparkTableOptimizerExecutor(
                SparkTableOptimizerExecutorSettings(
                    spark_submit=optimizer.worker.spark_submit,
                    submit_args=optimizer.worker.submit_args,
                    work_root=optimizer.work_root,
                    timeout_seconds=optimizer.worker.timeout_seconds,
                    terminate_grace_seconds=optimizer.worker.terminate_grace_seconds,
                    catalog_endpoint_url=optimizer.catalog_endpoint_url,
                    object_store_endpoint_url=settings.object_store.endpoint_url,
                    object_store_path_style=settings.object_store.s3_path_style,
                    region=settings.object_store.region,
                    access_key_id=settings.object_store.access_key_id,
                    secret_access_key=settings.object_store.secret_access_key,
                    catalog_name=optimizer.catalog_name,
                )
            )
        table_optimizer_runtime = TableOptimizerRuntime(
            application,
            table_optimizer_executor,
            poll_interval_seconds=settings.table_optimizers.poll_interval_seconds,
            max_concurrent_runs=settings.table_optimizers.max_concurrent_runs,
        )
    service_model = AwsServiceModel("glue")
    adapter = GlueAwsAdapter(
        application,
        settings.policy.default_catalog_id,
        settings.fault_injection,
    )
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
    sqlite_runtime_verification: SQLiteRuntimeVerification | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal sqlite_runtime_verification
        try:
            sqlite_runtime_verification = sqlite_runtime_verifier.verify()
            settings.data_root.mkdir(parents=True, exist_ok=True)
            settings.table_optimizers.work_root.mkdir(parents=True, exist_ok=True)
            await application.initialize()
            if table_optimizer_runtime is not None:
                await table_optimizer_runtime.start()
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.started",
                config_source=settings.config_source,
                config_fingerprint=settings.config_fingerprint,
                data_root=str(settings.data_root),
                catalog_database_file=str(settings.sqlite.database_file),
                catalog_journal_mode=settings.sqlite.journal_mode,
                catalog_busy_timeout_milliseconds=settings.sqlite.busy_timeout_milliseconds,
                sqlite_runtime=sqlite_runtime_verification.document(),
                operation_count=len(dispatcher.operations),
                operations=sorted(dispatcher.operations),
                runtime_profile={
                    "name": settings.runtime.name,
                    "spark_version": settings.runtime.spark_version,
                    "python_version": settings.runtime.python_version,
                    "java_version": settings.runtime.java_version,
                    "iceberg_version": settings.runtime.iceberg_version,
                },
                object_store_endpoint_scheme=object_store_endpoint.scheme,
                object_store_endpoint_host=object_store_endpoint.hostname,
                object_store_endpoint_port=object_store_endpoint.port,
                object_store_region=settings.object_store.region,
                object_store_path_style=settings.object_store.s3_path_style,
                fault_injection_enabled=settings.fault_injection.enabled,
                fault_rule_count=len(settings.fault_injection.rules),
                table_optimizer_enabled=settings.table_optimizers.enabled,
                table_optimizer_poll_interval_seconds=(
                    settings.table_optimizers.poll_interval_seconds
                ),
                table_optimizer_max_concurrent_runs=(settings.table_optimizers.max_concurrent_runs),
                table_optimizer_worker_timeout_seconds=(
                    settings.table_optimizers.worker.timeout_seconds
                ),
            )
            yield
        finally:
            try:
                if table_optimizer_runtime is not None:
                    await table_optimizer_runtime.close()
            finally:
                try:
                    if owned_metadata_store is not None:
                        await owned_metadata_store.close()
                finally:
                    log_event(_LOGGER, logging.INFO, "glue.stopping")

    app = FastAPI(
        title="Mystack Glue Data Catalog Emulator",
        version=distribution_version("mystack-glue"),
        lifespan=lifespan,
    )
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
                "table_optimizers_enabled": settings.table_optimizers.enabled,
                "sqlite_runtime": (
                    sqlite_runtime_verification.document()
                    if sqlite_runtime_verification is not None
                    else {"status": "not_started"}
                ),
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
