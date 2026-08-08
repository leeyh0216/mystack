"""Application-owned contracts consumed by Glue inbound adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from typing import Protocol

from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
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


class GlueManagementQueries(Protocol):
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
