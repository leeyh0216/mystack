"""Focused Glue database command and query handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Database.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteDatabase.html
"""

from __future__ import annotations

from mystack.glue.application.catalog_identity import database, name
from mystack.glue.application.catalog_ports import (
    CatalogQueryPort,
    CatalogReadPort,
    CatalogWritePort,
)
from mystack.glue.application.catalog_query_models import DatabasePageQuery
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.ports import Clock
from mystack.glue.domain import AlreadyExistsError, CatalogDatabase, InvalidInputError


class DatabaseCommands:
    def __init__(self, catalog: CatalogWritePort, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def create(self, catalog_id: str, definition: dict) -> CatalogDatabase:
        value = CatalogDatabase.create(catalog_id, definition, self._clock.now())
        key = (catalog_id, value.name)
        async with self._catalog.transaction(
            operation="create-database",
            resource_key=key,
        ) as transaction:
            if await transaction.find_database(catalog_id, value.name) is not None:
                raise AlreadyExistsError(f"Database {value.name!r} already exists")
            if not await transaction.insert_database(value):
                raise AlreadyExistsError(f"Database {value.name!r} already exists")
        return value

    async def update(self, catalog_id: str, old_name: str, definition: dict) -> None:
        normalized_old = name(old_name)
        revised_name = CatalogDatabase.definition_name(definition)
        old_key = (catalog_id, normalized_old)
        async with self._catalog.transaction(
            operation="update-database",
            resource_key=old_key,
        ) as transaction:
            current = await database(transaction, catalog_id, normalized_old)
            new_key = (catalog_id, revised_name)
            if (
                new_key != old_key
                and await transaction.find_database(catalog_id, revised_name) is not None
            ):
                raise AlreadyExistsError(f"Database {revised_name!r} already exists")
            revised = current.revise(definition)
            if new_key != old_key:
                for optimizer in await transaction.list_optimizers_for_database(
                    catalog_id,
                    normalized_old,
                ):
                    if optimizer.active_run is None:
                        continue
                    cancelled = optimizer.cancel_active_run(
                        now=self._clock.now(),
                        reason="Owning Glue database was renamed during optimizer execution",
                    )
                    if not await transaction.replace_optimizer(optimizer, cancelled):
                        raise RuntimeError(
                            "SQLite catalog optimizer changed during database rename"
                        )
            if not await transaction.replace_database(current, revised):
                if new_key != old_key:
                    raise AlreadyExistsError(f"Database {revised_name!r} already exists")
                raise RuntimeError("SQLite catalog database changed during update")

    async def delete(self, catalog_id: str, database_name: str) -> None:
        normalized = name(database_name)
        key = (catalog_id, normalized)
        async with self._catalog.transaction(
            operation="delete-database",
            resource_key=key,
        ) as transaction:
            current = await database(transaction, catalog_id, normalized)
            if not await transaction.delete_database(current):
                raise RuntimeError("SQLite catalog database changed during delete")


class DatabaseQueries:
    def __init__(
        self,
        read_catalog: CatalogReadPort,
        query_catalog: CatalogQueryPort,
        paginator: Paginator,
    ) -> None:
        self._read_catalog = read_catalog
        self._query_catalog = query_catalog
        self._paginator = paginator

    async def get(self, catalog_id: str, database_name: str) -> CatalogDatabase:
        normalized = name(database_name)
        return await database(self._read_catalog, catalog_id, normalized)

    async def list(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]:
        page_request = self._paginator.prepare_keyset(next_token, max_results).bind(
            self._paginator.context("databases", catalog_id)
        )
        page = await self._query_catalog.page_databases(
            DatabasePageQuery(catalog_id, page_request.size, page_request.cursor)
        )
        if page.invalid_cursor:
            raise InvalidInputError("Pagination token does not match this request")
        return list(page.values), self._paginator.complete_keyset(page_request, page.next_cursor)
