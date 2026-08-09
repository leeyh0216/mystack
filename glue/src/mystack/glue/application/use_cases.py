"""Application-owned contracts consumed by Glue inbound adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from typing import Protocol

from mystack.glue.application.batch import PartitionBatchFailure, PartitionBatchGetResult
from mystack.glue.application.table_optimizer import BatchTableOptimizerResult
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    TableOptimizer,
    TableOptimizerRun,
)


class GlueCatalogUseCases(Protocol):
    async def create_database(
        self,
        catalog_id: str,
        definition: dict,
    ) -> CatalogDatabase: ...

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase: ...

    async def get_databases(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]: ...

    async def update_database(
        self,
        catalog_id: str,
        old_name: str,
        definition: dict,
    ) -> None: ...

    async def delete_database(self, catalog_id: str, name: str) -> None: ...

    async def create_table(
        self,
        catalog_id: str,
        database_name: str,
        definition: dict,
    ) -> CatalogTable: ...

    async def create_open_table_format(
        self,
        catalog_id: str,
        database_name: str,
        table_name: object,
        iceberg_input: object,
    ) -> CatalogTable: ...

    async def get_table(
        self,
        catalog_id: str,
        database: str,
        name: str,
    ) -> CatalogTable: ...

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]: ...

    async def update_table(
        self,
        catalog_id: str,
        database: str,
        old_name: str,
        definition: dict,
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None: ...

    async def update_open_table_format(
        self,
        catalog_id: str,
        database: str,
        table_name: str,
        update_input: object,
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
    ) -> CatalogTableVersion: ...

    async def get_table_versions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTableVersion], str | None]: ...

    async def create_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definition: dict,
    ) -> CatalogPartition: ...

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition: ...

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
    ) -> tuple[list[CatalogPartition], str | None]: ...

    async def update_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        old_values: tuple[str, ...],
        definition: dict,
    ) -> None: ...

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None: ...

    async def batch_create_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definitions: list[dict],
    ) -> list[PartitionBatchFailure]: ...

    async def batch_get_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        value_groups: list[tuple[str, ...]],
    ) -> PartitionBatchGetResult: ...

    async def batch_update_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        entries: list[tuple[tuple[str, ...], dict]],
    ) -> list[PartitionBatchFailure]: ...

    async def batch_delete_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[PartitionBatchFailure]: ...

    async def create_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        configuration: object,
    ) -> None: ...

    async def update_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        configuration: object,
    ) -> None: ...

    async def delete_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
    ) -> None: ...

    async def get_table_optimizer(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
    ) -> TableOptimizer: ...

    async def batch_get_table_optimizers(
        self,
        entries: list[tuple[str, str, str, object]],
    ) -> BatchTableOptimizerResult: ...

    async def list_table_optimizer_runs(
        self,
        catalog_id: str,
        database: str,
        table: str,
        optimizer_type: object,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[TableOptimizerRun], str | None]: ...


class GlueManagementQueries(Protocol):
    """UI-only bounded pages, details, and explicit totals.

    The inbound management adapter may not reach persistence ports directly.
    """

    async def get_databases(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]: ...

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]: ...

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
    ) -> tuple[list[CatalogPartition], str | None]: ...

    async def count_databases(self, catalog_id: str) -> int: ...

    async def count_tables(self, catalog_id: str, database: str) -> int: ...

    async def count_partitions(self, catalog_id: str, database: str, table: str) -> int: ...

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable: ...
