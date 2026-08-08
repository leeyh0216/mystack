"""Stable Glue extension SPI version 1.

Glue Catalog behavior reference:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from mystack_aws_protocol import OperationMiddleware

from mystack_glue.application import CatalogApplication
from mystack_glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
)

from ._common import GlueExtensionIdentity


@dataclass(frozen=True, slots=True)
class CatalogDatabaseSnapshot:
    catalog_id: str
    name: str
    definition: MappingProxyType[str, Any]
    create_time: float


@dataclass(frozen=True, slots=True)
class CatalogTableVersionSnapshot:
    version_id: str
    definition: MappingProxyType[str, Any]
    create_time: float
    update_time: float


@dataclass(frozen=True, slots=True)
class CatalogTableSnapshot:
    catalog_id: str
    database_name: str
    name: str
    definition: MappingProxyType[str, Any]
    create_time: float
    update_time: float
    version_id: str
    archived_versions: tuple[CatalogTableVersionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class CatalogPartitionSnapshot:
    catalog_id: str
    database_name: str
    table_name: str
    values: tuple[str, ...]
    definition: MappingProxyType[str, Any]
    creation_time: float
    update_time: float


class GlueCatalogCapabilitiesV1(Protocol):
    async def create_database(
        self, catalog_id: str, definition: dict[str, Any]
    ) -> CatalogDatabaseSnapshot: ...

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabaseSnapshot: ...

    async def get_databases(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[tuple[CatalogDatabaseSnapshot, ...], str | None]: ...

    async def update_database(
        self, catalog_id: str, old_name: str, definition: dict[str, Any]
    ) -> None: ...

    async def delete_database(self, catalog_id: str, name: str) -> None: ...

    async def create_table(
        self,
        catalog_id: str,
        database: str,
        definition: dict[str, Any],
    ) -> CatalogTableSnapshot: ...

    async def get_table(
        self, catalog_id: str, database: str, name: str
    ) -> CatalogTableSnapshot: ...

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[tuple[CatalogTableSnapshot, ...], str | None]: ...

    async def update_table(
        self,
        catalog_id: str,
        database: str,
        old_name: str,
        definition: dict[str, Any],
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None: ...

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None: ...

    async def get_table_version(
        self,
        catalog_id: str,
        database: str,
        table: str,
        version_id: str | None,
    ) -> CatalogTableVersionSnapshot: ...

    async def get_table_versions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[tuple[CatalogTableVersionSnapshot, ...], str | None]: ...

    async def create_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definition: dict[str, Any],
    ) -> CatalogPartitionSnapshot: ...

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartitionSnapshot: ...

    async def get_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        *,
        expression: str | None,
        segment: tuple[int, int] | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[tuple[CatalogPartitionSnapshot, ...], str | None]: ...

    async def update_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        old_values: tuple[str, ...],
        definition: dict[str, Any],
    ) -> None: ...

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class GlueStableContextV1:
    identity: GlueExtensionIdentity
    catalog: GlueCatalogCapabilitiesV1
    default_catalog_id: str


class GlueStableExtensionProviderV1(Protocol):
    def __call__(self, context: GlueStableContextV1) -> OperationMiddleware: ...


class ApplicationCatalogCapabilitiesV1:
    """Stable snapshot facade backed only by application use cases."""

    def __init__(self, application: CatalogApplication) -> None:
        self._application = application

    async def create_database(self, catalog_id, definition):
        return _database(await self._application.create_database(catalog_id, definition))

    async def get_database(self, catalog_id, name):
        return _database(await self._application.get_database(catalog_id, name))

    async def get_databases(self, catalog_id, *, next_token, max_results):
        values, token = await self._application.get_databases(
            catalog_id, next_token=next_token, max_results=max_results
        )
        return tuple(map(_database, values)), token

    async def update_database(self, catalog_id, old_name, definition):
        await self._application.update_database(catalog_id, old_name, definition)

    async def delete_database(self, catalog_id, name):
        await self._application.delete_database(catalog_id, name)

    async def create_table(self, catalog_id, database, definition):
        return _table(await self._application.create_table(catalog_id, database, definition))

    async def get_table(self, catalog_id, database, name):
        return _table(await self._application.get_table(catalog_id, database, name))

    async def get_tables(self, catalog_id, database, *, expression, next_token, max_results):
        values, token = await self._application.get_tables(
            catalog_id,
            database,
            expression=expression,
            next_token=next_token,
            max_results=max_results,
        )
        return tuple(map(_table, values)), token

    async def update_table(
        self,
        catalog_id,
        database,
        old_name,
        definition,
        *,
        version_id,
        skip_archive,
    ):
        await self._application.update_table(
            catalog_id,
            database,
            old_name,
            definition,
            version_id=version_id,
            skip_archive=skip_archive,
        )

    async def delete_table(self, catalog_id, database, name):
        await self._application.delete_table(catalog_id, database, name)

    async def get_table_version(self, catalog_id, database, table, version_id):
        return _version(
            await self._application.get_table_version(catalog_id, database, table, version_id)
        )

    async def get_table_versions(self, catalog_id, database, table, *, next_token, max_results):
        values, token = await self._application.get_table_versions(
            catalog_id,
            database,
            table,
            next_token=next_token,
            max_results=max_results,
        )
        return tuple(map(_version, values)), token

    async def create_partition(self, catalog_id, database, table, definition):
        return _partition(
            await self._application.create_partition(catalog_id, database, table, definition)
        )

    async def get_partition(self, catalog_id, database, table, values):
        return _partition(
            await self._application.get_partition(catalog_id, database, table, values)
        )

    async def get_partitions(
        self,
        catalog_id,
        database,
        table,
        *,
        expression,
        segment,
        next_token,
        max_results,
    ):
        values, token = await self._application.get_partitions(
            catalog_id,
            database,
            table,
            expression=expression,
            segment=segment,
            next_token=next_token,
            max_results=max_results,
        )
        return tuple(map(_partition, values)), token

    async def update_partition(self, catalog_id, database, table, old_values, definition):
        await self._application.update_partition(
            catalog_id, database, table, old_values, definition
        )

    async def delete_partition(self, catalog_id, database, table, values):
        await self._application.delete_partition(catalog_id, database, table, values)


def _document(value: dict[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return copy.deepcopy(value)


def _database(value: CatalogDatabase) -> CatalogDatabaseSnapshot:
    return CatalogDatabaseSnapshot(
        value.catalog_id, value.name, _document(value.definition), value.create_time
    )


def _version(value: CatalogTableVersion) -> CatalogTableVersionSnapshot:
    return CatalogTableVersionSnapshot(
        value.version_id,
        _document(value.definition),
        value.create_time,
        value.update_time,
    )


def _table(value: CatalogTable) -> CatalogTableSnapshot:
    return CatalogTableSnapshot(
        value.catalog_id,
        value.database_name,
        value.name,
        _document(value.definition),
        value.create_time,
        value.update_time,
        value.version_id,
        tuple(map(_version, value.archived_versions)),
    )


def _partition(value: CatalogPartition) -> CatalogPartitionSnapshot:
    return CatalogPartitionSnapshot(
        value.catalog_id,
        value.database_name,
        value.table_name,
        value.values,
        _document(value.definition),
        value.creation_time,
        value.update_time,
    )
