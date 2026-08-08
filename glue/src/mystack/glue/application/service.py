"""Compatibility facade over focused Glue application handlers.

Reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

from dataclasses import dataclass

from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
)
from mystack.glue.domain.repositories import CatalogRepository

from .batch import PartitionBatchFailure, PartitionBatchHandler
from .database import DatabaseCommands, DatabaseQueries
from .initialization import CatalogInitializer
from .pagination import Paginator
from .partition import PartitionCommands, PartitionQueries
from .ports import Clock
from .table import TableCommands, TableQueries, TableVersionQueries


@dataclass(frozen=True, slots=True)
class CatalogPolicy:
    default_catalog_id: str
    api_page_size: int
    create_default_database: bool


class CatalogApplication:
    """Delegate the stable inbound surface without implementing catalog policy."""

    def __init__(
        self,
        repository: CatalogRepository,
        clock: Clock,
        policy: CatalogPolicy,
    ) -> None:
        paginator = Paginator(policy.api_page_size)
        self._database_commands = DatabaseCommands(repository, clock)
        self._database_queries = DatabaseQueries(repository, paginator)
        self._table_commands = TableCommands(repository, clock)
        self._table_queries = TableQueries(repository, paginator)
        self._table_versions = TableVersionQueries(self._table_queries, paginator)
        self._partition_commands = PartitionCommands(repository, clock)
        self._partition_queries = PartitionQueries(repository, paginator)
        self._partition_batches = PartitionBatchHandler(
            self._partition_commands,
            self._partition_queries,
        )
        self._initializer = CatalogInitializer(
            self._database_commands,
            self._database_queries,
            catalog_id=policy.default_catalog_id,
            create_default_database=policy.create_default_database,
        )

    async def initialize(self) -> None:
        await self._initializer.initialize()

    async def create_database(self, catalog_id: str, definition: dict) -> CatalogDatabase:
        return await self._database_commands.create(catalog_id, definition)

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase:
        return await self._database_queries.get(catalog_id, name)

    async def get_databases(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]:
        return await self._database_queries.list(
            catalog_id,
            next_token=next_token,
            max_results=max_results,
        )

    async def update_database(
        self,
        catalog_id: str,
        old_name: str,
        definition: dict,
    ) -> None:
        await self._database_commands.update(catalog_id, old_name, definition)

    async def delete_database(self, catalog_id: str, name: str) -> None:
        await self._database_commands.delete(catalog_id, name)

    async def create_table(
        self,
        catalog_id: str,
        database_name: str,
        definition: dict,
    ) -> CatalogTable:
        return await self._table_commands.create(catalog_id, database_name, definition)

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable:
        return await self._table_queries.get(catalog_id, database, name)

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]:
        return await self._table_queries.list(
            catalog_id,
            database,
            expression=expression,
            next_token=next_token,
            max_results=max_results,
        )

    async def update_table(
        self,
        catalog_id: str,
        database: str,
        old_name: str,
        definition: dict,
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None:
        await self._table_commands.update(
            catalog_id,
            database,
            old_name,
            definition,
            version_id=version_id,
            skip_archive=skip_archive,
        )

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None:
        await self._table_commands.delete(catalog_id, database, name)

    async def get_table_version(
        self,
        catalog_id: str,
        database: str,
        table: str,
        version_id: str | None,
    ) -> CatalogTableVersion:
        return await self._table_versions.get(
            catalog_id,
            database,
            table,
            version_id,
        )

    async def get_table_versions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTableVersion], str | None]:
        return await self._table_versions.list(
            catalog_id,
            database,
            table,
            next_token=next_token,
            max_results=max_results,
        )

    async def create_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definition: dict,
    ) -> CatalogPartition:
        return await self._partition_commands.create(
            catalog_id,
            database,
            table,
            definition,
        )

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        return await self._partition_queries.get(
            catalog_id,
            database,
            table,
            values,
        )

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
    ) -> tuple[list[CatalogPartition], str | None]:
        return await self._partition_queries.list(
            catalog_id,
            database,
            table,
            expression=expression,
            segment=segment,
            next_token=next_token,
            max_results=max_results,
        )

    async def update_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        old_values: tuple[str, ...],
        definition: dict,
    ) -> None:
        await self._partition_commands.update(
            catalog_id,
            database,
            table,
            old_values,
            definition,
        )

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None:
        await self._partition_commands.delete(
            catalog_id,
            database,
            table,
            values,
        )

    async def batch_create_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definitions: list[dict],
    ) -> list[PartitionBatchFailure]:
        return await self._partition_batches.create(
            catalog_id,
            database,
            table,
            definitions,
        )

    async def batch_get_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[CatalogPartition]:
        return await self._partition_batches.get(
            catalog_id,
            database,
            table,
            value_groups,
        )

    async def batch_update_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        entries: list[tuple[tuple[str, ...], dict]],
    ) -> list[PartitionBatchFailure]:
        return await self._partition_batches.update(
            catalog_id,
            database,
            table,
            entries,
        )

    async def batch_delete_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[PartitionBatchFailure]:
        return await self._partition_batches.delete(
            catalog_id,
            database,
            table,
            value_groups,
        )
