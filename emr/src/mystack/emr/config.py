"""EMR configuration adapter for the versioned Mystack YAML document.

References:
- https://docs.docker.com/reference/compose-file/configs/
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-release-app-versions-7.x.html
- https://spark.apache.org/docs/3.5.4/configuration.html
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mystack.aws_protocol.configuration import (
    ConfigurationError,
    LoadedConfiguration,
    require_mapping,
)
from mystack.emr.application import EmrPolicy, ReleaseProfile


@dataclass(frozen=True, slots=True)
class ObjectStoreSettings:
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    s3_path_style: bool


@dataclass(frozen=True, slots=True)
class SparkRuntimeSettings:
    spark_submit: str
    master: str
    packages: tuple[str, ...]
    conf: tuple[tuple[str, str], ...]
    submit_aliases: tuple[str, ...]
    option_value_names: frozenset[str]


@dataclass(frozen=True, slots=True)
class LogDeliverySettings:
    live_chunk_bytes: int
    retention_seconds: float
    publication_max_attempts: int
    publication_initial_backoff_seconds: float
    publication_max_backoff_seconds: float
    publication_attempt_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class SparkUiSettings:
    port_min: int
    port_max: int


@dataclass(frozen=True, slots=True)
class EmrSettings:
    listen_host: str
    listen_port: int
    work_root: Path
    process_timeout_seconds: float
    bootstrap_timeout_seconds: float
    bootstrap_shell: str
    terminate_grace_seconds: float
    shutdown_timeout_seconds: float
    output_tail_bytes: int
    log_delivery: LogDeliverySettings
    spark_ui: SparkUiSettings
    startup_clusters_file: Path | None
    command_runner_jars: frozenset[str]
    account_id: str
    object_store: ObjectStoreSettings
    runtimes: dict[str, SparkRuntimeSettings]
    policy: EmrPolicy
    config_source: str
    config_fingerprint: str

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> EmrSettings:
        emr = require_mapping(loaded.document, "emr")
        listen = require_mapping(emr, "listen")
        localstack = require_mapping(loaded.document, "localstack")
        all_runtime_documents = require_mapping(loaded.document, "runtime_profiles")
        release_documents = require_mapping(emr, "release_profiles")
        log_publication = require_mapping(emr, "log_publication")
        spark_ui = require_mapping(emr, "spark_ui")

        releases: dict[str, ReleaseProfile] = {}
        runtimes: dict[str, SparkRuntimeSettings] = {}
        for release_label, raw_release in release_documents.items():
            release = _mapping(raw_release, f"emr.release_profiles.{release_label}")
            runtime_name = str(release["runtime_profile"])
            raw_runtime = _mapping(
                all_runtime_documents.get(runtime_name),
                f"runtime_profiles.{runtime_name}",
            )
            releases[str(release_label)] = ReleaseProfile(
                release_label=str(release_label),
                runtime_profile=runtime_name,
                aws_spark_version=str(release["aws_spark_version"]),
                source=str(release["source"]),
            )
            runtimes[runtime_name] = _runtime(raw_runtime, runtime_name)

        try:
            default_release = str(emr["default_release_label"])
            if default_release not in releases:
                raise ConfigurationError(
                    "emr.default_release_label must name an emr.release_profiles entry"
                )
            spark_ui_settings = SparkUiSettings(
                port_min=int(spark_ui["port_min"]), port_max=int(spark_ui["port_max"])
            )
            if spark_ui_settings.port_min > spark_ui_settings.port_max:
                raise ConfigurationError("emr.spark_ui.port_min must not exceed port_max")
            return cls(
                listen_host=str(listen["host"]),
                listen_port=int(listen["port"]),
                work_root=Path(str(emr["work_root"])),
                process_timeout_seconds=float(emr["process_timeout_seconds"]),
                bootstrap_timeout_seconds=float(emr["bootstrap_timeout_seconds"]),
                bootstrap_shell=str(emr["bootstrap_shell"]),
                terminate_grace_seconds=float(emr["terminate_grace_seconds"]),
                shutdown_timeout_seconds=float(emr["shutdown_timeout_seconds"]),
                output_tail_bytes=int(emr["output_tail_bytes"]),
                log_delivery=LogDeliverySettings(
                    live_chunk_bytes=int(emr["live_log_chunk_bytes"]),
                    retention_seconds=float(emr["log_retention_seconds"]),
                    publication_max_attempts=int(log_publication["max_attempts"]),
                    publication_initial_backoff_seconds=float(
                        log_publication["initial_backoff_seconds"]
                    ),
                    publication_max_backoff_seconds=float(log_publication["max_backoff_seconds"]),
                    publication_attempt_timeout_seconds=float(
                        log_publication["attempt_timeout_seconds"]
                    ),
                ),
                spark_ui=spark_ui_settings,
                startup_clusters_file=_optional_path(
                    emr["startup_clusters_file"],
                    configuration_source=Path(loaded.source),
                ),
                command_runner_jars=frozenset(map(str, emr["command_runner_jars"])),
                account_id=str(localstack["account_id"]),
                object_store=ObjectStoreSettings(
                    endpoint_url=str(localstack["endpoint_url"]),
                    region=str(localstack["region"]),
                    access_key_id=str(localstack["access_key_id"]),
                    secret_access_key=str(localstack["secret_access_key"]),
                    s3_path_style=bool(localstack["s3_path_style"]),
                ),
                runtimes=runtimes,
                policy=EmrPolicy(
                    api_page_size=int(emr["api_page_size"]),
                    max_active_steps=int(emr["max_active_steps"]),
                    default_release_label=default_release,
                    release_profiles=releases,
                ),
                config_source=loaded.source,
                config_fingerprint=loaded.fingerprint,
            )
        except KeyError as error:
            raise ConfigurationError(
                f"EMR configuration is missing required key: {error.args[0]}"
            ) from error


def _runtime(document: dict[str, Any], name: str) -> SparkRuntimeSettings:
    try:
        raw_conf = _mapping(document["spark_conf"], f"runtime_profiles.{name}.spark_conf")
        return SparkRuntimeSettings(
            spark_submit=str(document["spark_submit"]),
            master=str(document["master"]),
            packages=tuple(map(str, document.get("spark_packages", ()))),
            conf=tuple((str(key), str(value)) for key, value in raw_conf.items()),
            submit_aliases=tuple(map(str, document["submit_aliases"])),
            option_value_names=frozenset(map(str, document["option_value_names"])),
        )
    except KeyError as error:
        raise ConfigurationError(
            f"Runtime profile {name!r} is missing required key: {error.args[0]}"
        ) from error


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section {path!r} must be a mapping")
    return value


def _optional_path(value: object, *, configuration_source: Path) -> Path | None:
    if value is None:
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else configuration_source.parent / path
