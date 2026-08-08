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
from mystack.glue.application import CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.policies import GlueFaultInjectionPolicy, GlueFaultRule


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
class GlueSettings:
    listen_host: str
    listen_port: int
    data_root: Path
    state_file: Path
    catalog_lock: GlueCatalogLockSettings
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
        fault_injection = require_mapping(glue, "fault_injection")
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
            lock_timeout_seconds = float(catalog_lock["acquire_timeout_seconds"])
            lock_poll_interval_seconds = float(catalog_lock["poll_interval_seconds"])
            if lock_file.resolve(strict=False) == state_file.resolve(strict=False):
                raise ConfigurationError("glue.catalog_lock.file must differ from glue.state_file")
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
