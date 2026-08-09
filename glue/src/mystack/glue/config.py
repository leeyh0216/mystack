"""Glue file configuration adapter.

References:
- https://docs.docker.com/reference/compose-file/configs/
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mystack.aws_protocol.configuration import (
    ConfigurationError,
    LoadedConfiguration,
    require_mapping,
)
from mystack.glue.application import CatalogPolicy, TableOptimizerPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.policies import GlueFaultInjectionPolicy, GlueFaultRule
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)


@dataclass(frozen=True, slots=True)
class GlueRuntimeProfile:
    name: str
    base_image: str
    spark_version: str
    python_version: str
    java_version: str
    iceberg_version: str


@dataclass(frozen=True, slots=True)
class GlueCatalogLockSettings:
    """Bounded inter-process lock settings for the durable catalog file."""

    lock_file: Path
    acquire_timeout_seconds: float
    poll_interval_seconds: float


@dataclass(frozen=True, slots=True)
class GlueObjectStoreSettings:
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    s3_path_style: bool


@dataclass(frozen=True, slots=True)
class GlueTableOptimizerWorkerSettings:
    spark_submit: Path
    submit_args: tuple[str, ...]
    timeout_seconds: float
    terminate_grace_seconds: float

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.terminate_grace_seconds <= 0:
            raise ConfigurationError("Glue table optimizer worker timeouts must be positive")


@dataclass(frozen=True, slots=True)
class GlueTableOptimizerSettings:
    enabled: bool
    work_root: Path
    catalog_endpoint_url: str
    catalog_name: str
    poll_interval_seconds: float
    max_concurrent_runs: int
    policy: TableOptimizerPolicy
    worker: GlueTableOptimizerWorkerSettings

    def __post_init__(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise ConfigurationError("Glue table optimizer poll interval must be positive")
        if self.max_concurrent_runs <= 0:
            raise ConfigurationError("Glue table optimizer concurrency must be positive")
        if not self.catalog_endpoint_url.startswith(("http://", "https://")):
            raise ConfigurationError("Glue optimizer catalog endpoint must be an HTTP URL")
        if not self.catalog_name.strip():
            raise ConfigurationError("Glue optimizer catalog name cannot be empty")


@dataclass(frozen=True, slots=True)
class GlueSettings:
    listen_host: str
    listen_port: int
    data_root: Path
    state_file: Path
    catalog_lock: GlueCatalogLockSettings
    sqlite: SQLiteRuntimeSettings
    object_store: GlueObjectStoreSettings
    table_optimizers: GlueTableOptimizerSettings
    default_region: str
    runtime: GlueRuntimeProfile
    policy: CatalogPolicy
    fault_injection: GlueFaultInjectionPolicy
    config_source: str
    config_fingerprint: str

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> GlueSettings:
        glue = require_mapping(loaded.document, "glue")
        listen = require_mapping(glue, "listen")
        profiles = require_mapping(loaded.document, "runtime_profiles")
        localstack = require_mapping(loaded.document, "localstack")
        expression = require_mapping(glue, "partition_expressions")
        catalog_lock = require_mapping(glue, "catalog_lock")
        sqlite = require_mapping(glue, "sqlite")
        sqlite_driver = require_mapping(sqlite, "driver")
        sqlite_checkpoint = require_mapping(sqlite, "checkpoint")
        fault_injection = require_mapping(glue, "fault_injection")
        table_optimizers = require_mapping(glue, "table_optimizers")
        optimizer_scheduler = require_mapping(table_optimizers, "scheduler")
        optimizer_worker = require_mapping(table_optimizers, "worker")
        try:
            runtime_name = str(glue["runtime_profile"])
            runtime = require_mapping(profiles, runtime_name)
            data_root = Path(str(glue["data_root"]))
            configured_state_file = Path(str(glue["state_file"]))
            state_file = (
                configured_state_file
                if configured_state_file.is_absolute()
                else data_root / configured_state_file
            )
            configured_lock_file = Path(str(catalog_lock["file"]))
            lock_file = (
                configured_lock_file
                if configured_lock_file.is_absolute()
                else data_root / configured_lock_file
            )
            configured_database_file = Path(str(sqlite["database_file"]))
            database_file = (
                configured_database_file
                if configured_database_file.is_absolute()
                else data_root / configured_database_file
            )
            configured_manifest_file = Path(str(sqlite_driver["manifest_file"]))
            manifest_file = (
                configured_manifest_file
                if configured_manifest_file.is_absolute()
                else Path(loaded.source).parent / configured_manifest_file
            )
            lock_timeout_seconds = float(catalog_lock["acquire_timeout_seconds"])
            lock_poll_interval_seconds = float(catalog_lock["poll_interval_seconds"])
            configured_optimizer_root = Path(str(table_optimizers["work_root"]))
            optimizer_root = (
                configured_optimizer_root
                if configured_optimizer_root.is_absolute()
                else data_root / configured_optimizer_root
            )
            if lock_file.resolve(strict=False) == state_file.resolve(strict=False):
                raise ConfigurationError("glue.catalog_lock.file must differ from glue.state_file")
            if database_file.resolve(strict=False) == state_file.resolve(strict=False):
                raise ConfigurationError(
                    "glue.sqlite.database_file must differ from glue.state_file"
                )
            if lock_poll_interval_seconds > lock_timeout_seconds:
                raise ConfigurationError(
                    "glue.catalog_lock.poll_interval_seconds must be no greater than "
                    "glue.catalog_lock.acquire_timeout_seconds"
                )
            return cls(
                listen_host=str(listen["host"]),
                listen_port=int(listen["port"]),
                data_root=data_root,
                state_file=state_file,
                catalog_lock=GlueCatalogLockSettings(
                    lock_file=lock_file,
                    acquire_timeout_seconds=lock_timeout_seconds,
                    poll_interval_seconds=lock_poll_interval_seconds,
                ),
                sqlite=SQLiteRuntimeSettings(
                    database_file=database_file,
                    driver=SQLiteDriverSettings(
                        module=str(sqlite_driver["module"]),
                        expected_version=str(sqlite_driver["expected_version"]),
                        minimum_wal_version=str(sqlite_driver["minimum_wal_version"]),
                        manifest_file=manifest_file,
                    ),
                    journal_mode=str(sqlite["journal_mode"]),
                    synchronous=str(sqlite["synchronous"]),
                    busy_timeout_milliseconds=int(sqlite["busy_timeout_milliseconds"]),
                    retry_limit=int(sqlite["retry_limit"]),
                    checkpoint=SQLiteCheckpointSettings(
                        mode=str(sqlite_checkpoint["mode"]),
                        auto_checkpoint_pages=int(sqlite_checkpoint["auto_checkpoint_pages"]),
                    ),
                ),
                object_store=GlueObjectStoreSettings(
                    endpoint_url=str(localstack["endpoint_url"]),
                    region=str(localstack["region"]),
                    access_key_id=str(localstack["access_key_id"]),
                    secret_access_key=str(localstack["secret_access_key"]),
                    s3_path_style=bool(localstack["s3_path_style"]),
                ),
                table_optimizers=GlueTableOptimizerSettings(
                    enabled=bool(table_optimizers["enabled"]),
                    work_root=optimizer_root,
                    catalog_endpoint_url=str(table_optimizers["catalog_endpoint_url"]),
                    catalog_name=str(table_optimizers["catalog_name"]),
                    poll_interval_seconds=float(optimizer_scheduler["poll_interval_seconds"]),
                    max_concurrent_runs=int(optimizer_scheduler["max_concurrent_runs"]),
                    policy=TableOptimizerPolicy(
                        initial_delay_seconds=float(optimizer_scheduler["initial_delay_seconds"]),
                        compaction_interval_seconds=float(
                            optimizer_scheduler["compaction_interval_seconds"]
                        ),
                        history_limit=int(optimizer_scheduler["history_limit"]),
                        compaction_failure_limit=int(
                            optimizer_scheduler["compaction_failure_limit"]
                        ),
                    ),
                    worker=GlueTableOptimizerWorkerSettings(
                        spark_submit=Path(str(optimizer_worker["spark_submit"])),
                        submit_args=tuple(map(str, optimizer_worker["submit_args"])),
                        timeout_seconds=float(optimizer_worker["timeout_seconds"]),
                        terminate_grace_seconds=float(optimizer_worker["terminate_grace_seconds"]),
                    ),
                ),
                default_region=str(localstack["region"]),
                runtime=GlueRuntimeProfile(
                    name=runtime_name,
                    base_image=str(runtime["base_image"]),
                    spark_version=str(runtime["spark_version"]),
                    python_version=str(runtime["python_version"]),
                    java_version=str(runtime["java_version"]),
                    iceberg_version=str(runtime["iceberg_version"]),
                ),
                policy=CatalogPolicy(
                    default_catalog_id=str(glue["catalog_id"]),
                    api_page_size=int(glue["api_page_size"]),
                    create_default_database=bool(glue["create_default_database"]),
                    partition_expressions=PartitionExpressionPolicy(
                        max_length=int(expression["max_length"]),
                        max_tokens=int(expression["max_tokens"]),
                        supported_key_types=tuple(
                            str(value) for value in expression["supported_key_types"]
                        ),
                    ),
                ),
                fault_injection=GlueFaultInjectionPolicy(
                    enabled=bool(fault_injection["enabled"]),
                    rules=tuple(
                        _fault_rule(value, index)
                        for index, value in enumerate(fault_injection["rules"])
                    ),
                ),
                config_source=loaded.source,
                config_fingerprint=loaded.fingerprint,
            )
        except KeyError as error:
            raise ConfigurationError(
                f"Glue configuration is missing required key: {error.args[0]}"
            ) from error
        except ValueError as error:
            if isinstance(error, ConfigurationError):
                raise
            raise ConfigurationError(str(error)) from error


def _fault_rule(value: object, index: int) -> GlueFaultRule:
    if not isinstance(value, dict):
        raise ConfigurationError(f"glue.fault_injection.rules[{index}] must be a mapping")
    try:
        return GlueFaultRule(
            rule_id=str(value["id"]),
            operation=str(value["operation"]),
            error_code=str(value["error_code"]),
            message=str(value["message"]),
        )
    except KeyError as error:
        raise ConfigurationError(
            f"glue.fault_injection.rules[{index}] is missing required key: {error.args[0]}"
        ) from error
