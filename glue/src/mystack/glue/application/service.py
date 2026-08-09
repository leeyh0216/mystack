"""Compatibility facade over focused Glue application handlers.

Reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

from dataclasses import dataclass

from mystack.glue.application.batch import (
    PartitionBatchFailure,
    PartitionBatchGetResult,
    PartitionBatchHandler,
)
from mystack.glue.application.catalog_ports import CatalogReadPort, CatalogWritePort
from mystack.glue.application.database import DatabaseCommands, DatabaseQueries
from mystack.glue.application.iceberg_commit import IcebergCommitObserver
from mystack.glue.application.initialization import CatalogInitializer
from mystack.glue.application.open_table_format import OpenTableFormatCommands
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.partition import (
    PartitionCommands,
    PartitionQueries,
    PartitionTargetResolver,
)
from mystack.glue.application.partition_expression import (
    PartitionExpressionCompiler,
    PartitionExpressionPolicy,
)
from mystack.glue.application.ports import Clock, IcebergMetadataStore, IdentifierGenerator
from mystack.glue.application.table import TableCommands, TableQueries, TableVersionQueries
from mystack.glue.application.table_optimizer import (
    BatchTableOptimizerResult,
    TableOptimizerCommands,
    TableOptimizerPolicy,
    TableOptimizerQueries,
)
from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    IcebergOpenTableFormatPlanner,
    TableOptimizer,
    TableOptimizerRun,
)


@dataclass(frozen=True, slots=True)
class CatalogPolicy:
    default_catalog_id: str
    api_page_size: int
    create_default_database: bool
    partition_expressions: PartitionExpressionPolicy


class CatalogApplication:
    """Delegate the stable inbound surface without implementing catalog policy."""

    def __init__(
        self,
        read_catalog: CatalogReadPort,
        write_catalog: CatalogWritePort,
        clock: Clock,
        policy: CatalogPolicy,
        *,
        iceberg_metadata_store: IcebergMetadataStore,
        identifier_generator: IdentifierGenerator,
        table_optimizer_policy: TableOptimizerPolicy | None = None,
    ) -> None:
        paginator = Paginator(policy.api_page_size)
        self._write_catalog = write_catalog
        self._database_commands = DatabaseCommands(write_catalog, clock)
        self._database_queries = DatabaseQueries(read_catalog, paginator)
        self._table_commands = TableCommands(write_catalog, clock, IcebergCommitObserver())
        self._table_queries = TableQueries(read_catalog, paginator)
        self._table_versions = TableVersionQueries(self._table_queries, paginator)
        self._open_table_format = OpenTableFormatCommands(
            databases=self._database_queries,
            tables=self._table_queries,
            table_commands=self._table_commands,
            metadata_store=iceberg_metadata_store,
            identifiers=identifier_generator,
            clock=clock,
            planner=IcebergOpenTableFormatPlanner(),
        )
        self._partition_commands = PartitionCommands(write_catalog, clock)
        self._partition_queries = PartitionQueries(
            read_catalog,
            paginator,
            PartitionExpressionCompiler(policy.partition_expressions),
        )
        self._partition_batches = PartitionBatchHandler(
            self._partition_commands,
            self._partition_queries,
            PartitionTargetResolver(read_catalog),
        )
        optimizer_policy = table_optimizer_policy or TableOptimizerPolicy(
            initial_delay_seconds=30.0,
            compaction_interval_seconds=24 * 3600.0,
            history_limit=100,
            compaction_failure_limit=4,
        )
        self._table_optimizer_commands = TableOptimizerCommands(
            write_catalog,
            clock,
            identifier_generator,
            optimizer_policy,
        )
        self._table_optimizer_queries = TableOptimizerQueries(read_catalog, paginator)
        self._initializer = CatalogInitializer(
            self._database_commands,
            self._database_queries,
            catalog_id=policy.default_catalog_id,
            create_default_database=policy.create_default_database,
        )

    async def initialize(self) -> None:
        await self._write_catalog.initialize()
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

    async def create_open_table_format(
        self,
        catalog_id: str,
        database_name: str,
        table_name: object,
        iceberg_input: object,
    ) -> CatalogTable:
        return await self._open_table_format.create(
            catalog_id,
            database_name,
            table_name,
            iceberg_input,
        )

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

    async def update_open_table_format(
        self,
        catalog_id: str,
        database: str,
        table_name: str,
        update_input: object,
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None:
        await self._open_table_format.update(
            catalog_id,
            database,
            table_name,
            update_input,
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
    ) -> PartitionBatchGetResult:
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

    async def create_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        configuration: object,
    ) -> None:
        await self._table_optimizer_commands.create(
            catalog_id, database, table, optimizer_type, configuration
        )

    async def update_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        configuration: object,
    ) -> None:
        await self._table_optimizer_commands.update(
            catalog_id, database, table, optimizer_type, configuration
        )

    async def delete_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
    ) -> None:
        await self._table_optimizer_commands.delete(catalog_id, database, table, optimizer_type)

    async def get_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
    ) -> TableOptimizer:
        return await self._table_optimizer_queries.get(catalog_id, database, table, optimizer_type)

    async def batch_get_table_optimizers(
        self,
        entries: list[tuple[str, str, str, object]],
    ) -> BatchTableOptimizerResult:
        return await self._table_optimizer_queries.batch_get(entries)

    async def list_table_optimizer_runs(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[TableOptimizerRun], str | None]:
        return await self._table_optimizer_queries.list_runs(
            catalog_id,
            database,
            table,
            optimizer_type,
            next_token=next_token,
            max_results=max_results,
        )

    async def recover_interrupted_table_optimizer_runs(self, reason: str) -> int:
        return await self._table_optimizer_commands.recover_interrupted(reason)

    async def claim_due_table_optimizer_work(self, maximum: int) -> list[TableOptimizerWork]:
        return await self._table_optimizer_commands.claim_due(maximum)

    async def mark_table_optimizer_in_progress(self, work: TableOptimizerWork) -> bool:
        return await self._table_optimizer_commands.mark_in_progress(work)

    async def complete_table_optimizer(
        self,
        work: TableOptimizerWork,
        metrics: dict,
    ) -> bool:
        return await self._table_optimizer_commands.complete(work, metrics)

    async def fail_table_optimizer(self, work: TableOptimizerWork, error: str) -> bool:
        return await self._table_optimizer_commands.fail(work, error)

    async def is_table_optimizer_work_current(self, work: TableOptimizerWork) -> bool:
        return await self._table_optimizer_queries.is_current(work)
