"""Application-owned Glue Catalog persistence ports.

The application decides Glue validation and error precedence.  Implementations only store and
retrieve immutable domain values; they never expose a mutable aggregate, SQL, or DB-API objects.

References:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
- https://www.sqlite.org/lang_transaction.html
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from mystack.glue.application.catalog_query_models import (
    CatalogPage,
    DatabasePageQuery,
    PartitionCatalogPage,
    PartitionPageQuery,
    TablePageQuery,
)
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    TableOptimizer,
)

CatalogResourceKey = tuple[object, ...]


class CatalogReadPort(Protocol):
    """Point lookups and optimizer reads required by commands and application policy."""

    async def find_database(
        self,
        catalog_id: str,
        database_name: str,
    ) -> CatalogDatabase | None: ...

    async def find_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogTable | None: ...

    async def find_partition(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> CatalogPartition | None: ...

    async def find_optimizer(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: str,
    ) -> TableOptimizer | None: ...

    async def list_optimizers_for_database(
        self,
        catalog_id: str,
        database_name: str,
    ) -> tuple[TableOptimizer, ...]: ...

    async def list_optimizers_for_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> tuple[TableOptimizer, ...]: ...

    async def list_active_optimizers(self) -> tuple[TableOptimizer, ...]: ...

    async def list_due_optimizers(
        self,
        now: float,
        maximum: int,
    ) -> tuple[TableOptimizer, ...]: ...


class CatalogQueryPort(Protocol):
    """Bounded Catalog pages and explicit management-only totals.

    A page is separate from lookup/command capability so application code cannot accidentally
    recover a full Catalog collection and paginate it in memory.
    """

    async def page_databases(
        self,
        query: DatabasePageQuery,
    ) -> CatalogPage[CatalogDatabase]: ...

    async def page_tables(self, query: TablePageQuery) -> CatalogPage[CatalogTable]: ...

    async def page_partitions(
        self,
        query: PartitionPageQuery,
    ) -> PartitionCatalogPage[CatalogPartition]: ...

    async def first_partition(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogPartition | None: ...

    async def count_databases(self, catalog_id: str) -> int: ...

    async def count_tables(self, catalog_id: str, database_name: str) -> int: ...

    async def count_partitions(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> int: ...


class CatalogTransaction(CatalogReadPort, Protocol):
    """Typed persistence operations scoped to one short write transaction.

    A ``False`` result describes a neutral conditional-write miss.  The application maps it to the
    correct Glue domain error after it has performed its documented validation sequence.
    """

    async def insert_database(self, value: CatalogDatabase) -> bool: ...

    async def replace_database(
        self,
        current: CatalogDatabase,
        revised: CatalogDatabase,
    ) -> bool: ...

    async def delete_database(self, value: CatalogDatabase) -> bool: ...

    async def insert_table(self, value: CatalogTable) -> bool: ...

    async def replace_table(
        self,
        current: CatalogTable,
        revised: CatalogTable,
    ) -> bool: ...

    async def delete_table(self, value: CatalogTable) -> bool: ...

    async def insert_partition(self, value: CatalogPartition) -> bool: ...

    async def replace_partition(
        self,
        current: CatalogPartition,
        revised: CatalogPartition,
    ) -> bool: ...

    async def delete_partition(self, value: CatalogPartition) -> bool: ...

    async def insert_optimizer(self, value: TableOptimizer) -> bool: ...

    async def replace_optimizer(
        self,
        current: TableOptimizer,
        revised: TableOptimizer,
    ) -> bool: ...

    async def delete_optimizer(self, value: TableOptimizer) -> bool: ...


class CatalogWritePort(Protocol):
    """Own short catalog write transactions without exposing infrastructure controls."""

    async def initialize(self) -> None: ...

    def transaction(
        self,
        *,
        operation: str,
        resource_key: CatalogResourceKey,
    ) -> AbstractAsyncContextManager[CatalogTransaction]: ...


class CatalogStore(CatalogReadPort, CatalogQueryPort, CatalogWritePort, Protocol):
    """Composition-root convenience type for an adapter that implements both ports."""
