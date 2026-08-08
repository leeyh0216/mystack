"""Repository port owned by the Glue domain.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from typing import Protocol

from .model import CatalogDatabase, CatalogPartition, CatalogTable, CatalogTableVersion


class CatalogRepository(Protocol):
    async def create_database(self, database: CatalogDatabase) -> None: ...

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase: ...

    async def list_databases(self, catalog_id: str) -> list[CatalogDatabase]: ...

    async def update_database(self, old_name: str, database: CatalogDatabase) -> None: ...

    async def delete_database(self, catalog_id: str, name: str) -> None: ...

    async def create_table(self, table: CatalogTable) -> None: ...

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable: ...

    async def list_tables(self, catalog_id: str, database: str) -> list[CatalogTable]: ...

    async def update_table(
        self,
        old_name: str,
        table: CatalogTable,
        *,
        expected_version_id: str | None,
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

    async def list_table_versions(
        self,
        catalog_id: str,
        database: str,
        table: str,
    ) -> list[CatalogTableVersion]: ...

    async def create_partition(self, partition: CatalogPartition) -> None: ...

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition: ...

    async def list_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
    ) -> list[CatalogPartition]: ...

    async def update_partition(
        self,
        old_values: tuple[str, ...],
        partition: CatalogPartition,
    ) -> None: ...

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None: ...
