"""Glue extension discovery and composition-root context injection.

Official plugin-discovery references:
- https://docs.python.org/3/library/importlib.metadata.html#entry-points
- https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import entry_points, version
from typing import Protocol

from mystack_aws_protocol import (
    AwsServiceModel,
    ConfigurationError,
    OperationExtensionBinding,
    OperationMiddleware,
)
from mystack_aws_protocol.observability import log_event

from .application import CatalogApplication
from .application.ports import Clock
from .config import GlueExtensionProviderSettings, GlueSettings
from .domain.repositories import CatalogRepository
from .extension_api import (
    GlueApplicationContextV1,
    GlueExtensionIdentity,
    GlueStableContextV1,
    GlueUnsafeContextV1,
)
from .extension_api.stable import ApplicationCatalogCapabilitiesV1

_LOGGER = logging.getLogger(__name__)
_SUPPORTED_API_VERSION = 1
_ENTRY_POINT_GROUPS = {
    "stable": "mystack.glue.extensions.stable.v1",
    "application": "mystack.glue.extensions.application.v1",
    "unsafe": "mystack.glue.extensions.unsafe.v1",
}


@dataclass(frozen=True, slots=True)
class LoadedExtensionFactory:
    factory: object
    distribution: str
    distribution_version: str


class ExtensionRegistry(Protocol):
    def load(self, group: str, name: str) -> LoadedExtensionFactory: ...


class ImportlibExtensionRegistry:
    """Discover installed providers through standard Python package metadata."""

    def load(self, group: str, name: str) -> LoadedExtensionFactory:
        matches = tuple(entry_points(group=group, name=name))
        if len(matches) != 1:
            raise ConfigurationError(
                f"Expected exactly one extension entry point {group}:{name}; found {len(matches)}"
            )
        selected = matches[0]
        distribution = selected.dist
        return LoadedExtensionFactory(
            factory=selected.load(),
            distribution=(distribution.name if distribution is not None else "<unknown>"),
            distribution_version=(
                distribution.version if distribution is not None else "<unknown>"
            ),
        )


def load_glue_extensions(
    *,
    settings: GlueSettings,
    service_model: AwsServiceModel,
    application: CatalogApplication,
    repository: CatalogRepository,
    clock: Clock,
    registry: ExtensionRegistry | None = None,
) -> tuple[OperationExtensionBinding, ...]:
    extension_settings = settings.extensions
    if not extension_settings.enabled:
        log_event(
            _LOGGER,
            logging.INFO,
            "extension.discovery.skipped",
            service="glue",
            configured_provider_count=len(extension_settings.providers),
            reason="disabled",
        )
        return ()

    registry = registry or ImportlibExtensionRegistry()
    providers = extension_settings.providers
    mystack_version = version("mystack-glue")
    validation_fields = {
        "service": "glue",
        "configured_provider_count": len(providers),
        "configured_provider_ids": [provider.extension_id for provider in providers],
        "mystack_version": mystack_version,
    }
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.configuration.validation.started",
        **validation_fields,
    )
    try:
        _validate_provider_set(providers, settings, service_model, mystack_version)
    except ConfigurationError:
        log_event(
            _LOGGER,
            logging.ERROR,
            "extension.configuration.validation.failed",
            **validation_fields,
            fix_hint=(
                "Inspect glue.extensions.providers, SPI compatibility versions, operation names, "
                "duplicate IDs, and unsafe permission."
            ),
        )
        raise
    log_event(
        _LOGGER,
        logging.INFO,
        "extension.configuration.validation.completed",
        **validation_fields,
    )
    stable_catalog = ApplicationCatalogCapabilitiesV1(application)
    bindings: list[OperationExtensionBinding] = []
    for provider in providers:
        group = _ENTRY_POINT_GROUPS[provider.spi]
        fields = {
            "service": "glue",
            "extension_id": provider.extension_id,
            "extension_spi": provider.spi,
            "extension_api_version": provider.api_version,
            "entry_point_group": group,
            "entry_point_name": provider.entry_point,
            "operations": list(provider.operations),
        }
        log_event(_LOGGER, logging.INFO, "extension.provider.load.started", **fields)
        try:
            loaded = registry.load(group, provider.entry_point)
            middleware = _create_middleware(
                provider,
                loaded,
                settings=settings,
                application=application,
                repository=repository,
                clock=clock,
                stable_catalog=stable_catalog,
                mystack_version=mystack_version,
            )
            binding = OperationExtensionBinding(
                extension_id=provider.extension_id,
                spi=provider.spi,
                operations=frozenset(provider.operations),
                priority=provider.priority,
                timeout_seconds=provider.timeout_seconds,
                middleware=middleware,
            )
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "extension.provider.load.failed",
                **fields,
                fix_hint=(
                    "Verify the mounted wheel, entry-point namespace/name, SPI API version, "
                    "provider callable, and unsafe permission settings."
                ),
                exc_info=True,
            )
            raise
        bindings.append(binding)
        log_event(
            _LOGGER,
            logging.INFO,
            "extension.provider.load.completed",
            **fields,
            distribution=loaded.distribution,
            distribution_version=loaded.distribution_version,
            priority=provider.priority,
            timeout_seconds=provider.timeout_seconds,
            mystack_version=mystack_version,
            compatibility_requirement=(
                provider.mystack_minor_version
                if provider.spi == "application"
                else provider.mystack_version
                if provider.spi == "unsafe"
                else f"spi-v{provider.api_version}"
            ),
        )
    return tuple(bindings)


def _validate_provider_set(
    providers: tuple[GlueExtensionProviderSettings, ...],
    settings: GlueSettings,
    service_model: AwsServiceModel,
    mystack_version: str,
) -> None:
    ids = [provider.extension_id for provider in providers]
    duplicates = sorted({extension_id for extension_id in ids if ids.count(extension_id) > 1})
    if duplicates:
        raise ConfigurationError(f"Duplicate Glue extension IDs: {', '.join(duplicates)}")
    official_operations = set(service_model.operation_names)
    for provider in providers:
        if provider.api_version != _SUPPORTED_API_VERSION:
            raise ConfigurationError(
                f"Unsupported {provider.spi} SPI api_version={provider.api_version} for "
                f"extension {provider.extension_id!r}; expected {_SUPPORTED_API_VERSION}"
            )
        invalid = sorted(set(provider.operations) - official_operations - {"*"})
        if invalid:
            raise ConfigurationError(
                f"Glue extension {provider.extension_id!r} selects unknown operations: "
                + ", ".join(invalid)
            )
        if provider.spi == "application":
            current_minor = ".".join(mystack_version.split(".", maxsplit=2)[:2])
            if provider.mystack_minor_version != current_minor:
                raise ConfigurationError(
                    f"Application Glue extension {provider.extension_id!r} requires "
                    f"mystack_minor_version={current_minor!r}; configured "
                    f"{provider.mystack_minor_version!r}"
                )
        if provider.spi == "unsafe":
            if not settings.extensions.allow_unsafe:
                raise ConfigurationError(
                    f"Glue extension {provider.extension_id!r} requests unsafe SPI while "
                    "glue.extensions.allow_unsafe is false"
                )
            if provider.mystack_version != mystack_version:
                raise ConfigurationError(
                    f"Unsafe Glue extension {provider.extension_id!r} requires exact "
                    f"mystack_version={mystack_version!r}; configured "
                    f"{provider.mystack_version!r}"
                )


def _create_middleware(
    provider: GlueExtensionProviderSettings,
    loaded: LoadedExtensionFactory,
    *,
    settings: GlueSettings,
    application: CatalogApplication,
    repository: CatalogRepository,
    clock: Clock,
    stable_catalog: ApplicationCatalogCapabilitiesV1,
    mystack_version: str,
) -> OperationMiddleware:
    factory = loaded.factory
    if not callable(factory):
        raise ConfigurationError(
            f"Glue extension entry point {provider.entry_point!r} is not callable"
        )
    identity = GlueExtensionIdentity(
        extension_id=provider.extension_id,
        entry_point=provider.entry_point,
        operations=provider.operations,
        api_version=provider.api_version,
    )
    if provider.spi == "stable":
        context = GlueStableContextV1(
            identity=identity,
            catalog=stable_catalog,
            default_catalog_id=settings.policy.default_catalog_id,
        )
    elif provider.spi == "application":
        context = GlueApplicationContextV1(
            identity=identity,
            application=application,
            default_catalog_id=settings.policy.default_catalog_id,
            mystack_version=mystack_version,
        )
    else:
        context = GlueUnsafeContextV1(
            identity=identity,
            application=application,
            repository=repository,
            clock=clock,
            settings=settings,
            mystack_version=mystack_version,
        )
    middleware = factory(context)
    if not callable(getattr(middleware, "invoke", None)):
        raise ConfigurationError(
            f"Glue extension {provider.extension_id!r} did not return OperationMiddleware"
        )
    return middleware
