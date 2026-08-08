"""Glue file configuration adapter.

References:
- https://docs.docker.com/reference/compose-file/configs/
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from mystack_aws_protocol.configuration import (
    ConfigurationError,
    LoadedConfiguration,
    require_mapping,
)

from .application import CatalogPolicy


@dataclass(frozen=True, slots=True)
class GlueRuntimeProfile:
    name: str
    base_image: str
    spark_version: str
    python_version: str
    java_version: str
    iceberg_version: str


ExtensionSpi = Literal["stable", "application", "unsafe"]


@dataclass(frozen=True, slots=True)
class GlueExtensionProviderSettings:
    extension_id: str
    spi: ExtensionSpi
    api_version: int
    entry_point: str
    operations: tuple[str, ...]
    priority: int
    timeout_seconds: float
    mystack_minor_version: str | None
    mystack_version: str | None


@dataclass(frozen=True, slots=True)
class GlueExtensionSettings:
    enabled: bool
    allow_unsafe: bool
    wheels_directory: Path
    install_directory: Path
    install_timeout_seconds: float
    providers: tuple[GlueExtensionProviderSettings, ...]


@dataclass(frozen=True, slots=True)
class GlueSettings:
    listen_host: str
    listen_port: int
    data_root: Path
    state_file: Path
    default_region: str
    runtime: GlueRuntimeProfile
    extensions: GlueExtensionSettings
    policy: CatalogPolicy
    config_source: str
    config_fingerprint: str

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> GlueSettings:
        glue = require_mapping(loaded.document, "glue")
        listen = require_mapping(glue, "listen")
        profiles = require_mapping(loaded.document, "runtime_profiles")
        localstack = require_mapping(loaded.document, "localstack")
        extensions = require_mapping(glue, "extensions")
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
            return cls(
                listen_host=str(listen["host"]),
                listen_port=int(listen["port"]),
                data_root=data_root,
                state_file=state_file,
                default_region=str(localstack["region"]),
                runtime=GlueRuntimeProfile(
                    name=runtime_name,
                    base_image=str(runtime["base_image"]),
                    spark_version=str(runtime["spark_version"]),
                    python_version=str(runtime["python_version"]),
                    java_version=str(runtime["java_version"]),
                    iceberg_version=str(runtime["iceberg_version"]),
                ),
                extensions=GlueExtensionSettings(
                    enabled=bool(extensions["enabled"]),
                    allow_unsafe=bool(extensions["allow_unsafe"]),
                    wheels_directory=Path(str(extensions["wheels_directory"])),
                    install_directory=Path(str(extensions["install_directory"])),
                    install_timeout_seconds=float(extensions["install_timeout_seconds"]),
                    providers=tuple(
                        _extension_provider(provider) for provider in extensions["providers"]
                    ),
                ),
                policy=CatalogPolicy(
                    default_catalog_id=str(glue["catalog_id"]),
                    api_page_size=int(glue["api_page_size"]),
                    create_default_database=bool(glue["create_default_database"]),
                ),
                config_source=loaded.source,
                config_fingerprint=loaded.fingerprint,
            )
        except KeyError as error:
            raise ConfigurationError(
                f"Glue configuration is missing required key: {error.args[0]}"
            ) from error


def _extension_provider(value: object) -> GlueExtensionProviderSettings:
    if not isinstance(value, dict):
        raise ConfigurationError("Each glue.extensions.providers item must be a mapping")
    spi = str(value["spi"])
    if spi not in {"stable", "application", "unsafe"}:
        raise ConfigurationError(f"Unsupported Glue extension SPI: {spi}")
    return GlueExtensionProviderSettings(
        extension_id=str(value["id"]),
        spi=cast(ExtensionSpi, spi),
        api_version=int(value["api_version"]),
        entry_point=str(value["entry_point"]),
        operations=tuple(map(str, value["operations"])),
        priority=int(value["priority"]),
        timeout_seconds=float(value["timeout_seconds"]),
        mystack_minor_version=(
            str(value["mystack_minor_version"])
            if value.get("mystack_minor_version") is not None
            else None
        ),
        mystack_version=(
            str(value["mystack_version"]) if value.get("mystack_version") is not None else None
        ),
    )
