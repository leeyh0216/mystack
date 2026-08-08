"""Focused Glue database command and query handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Database.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteDatabase.html
"""

from __future__ import annotations

import copy

from mystack.glue.application.pagination import Paginator
from mystack.glue.application.ports import Clock
from mystack.glue.application.state import database, name, rename_database_children
from mystack.glue.domain import AlreadyExistsError, CatalogDatabase
from mystack.glue.domain.repositories import CatalogRepository


class DatabaseCommands:
    def __init__(self, repository: CatalogRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def create(self, catalog_id: str, definition: dict) -> CatalogDatabase:
        value = CatalogDatabase.create(catalog_id, definition, self._clock.now())
        key = (catalog_id, value.name)
        async with self._repository.transaction(
            operation="create-database",
            resource_key=key,
        ) as state:
            if key in state.databases:
                raise AlreadyExistsError(f"Database {value.name!r} already exists")
            state.databases[key] = copy.deepcopy(value)
        return value

    async def update(self, catalog_id: str, old_name: str, definition: dict) -> None:
        normalized_old = name(old_name)
        old_key = (catalog_id, normalized_old)
        async with self._repository.transaction(
            operation="update-database",
            resource_key=old_key,
        ) as state:
            current = database(state, catalog_id, normalized_old)
            revised = current.revise(definition)
            new_key = (catalog_id, revised.name)
            if new_key != old_key and new_key in state.databases:
                raise AlreadyExistsError(f"Database {revised.name!r} already exists")
            state.databases.pop(old_key)
            state.databases[new_key] = revised
            if new_key != old_key:
                rename_database_children(
                    state,
                    catalog_id,
                    normalized_old,
                    revised.name,
                )

    async def delete(self, catalog_id: str, database_name: str) -> None:
        normalized = name(database_name)
        key = (catalog_id, normalized)
        async with self._repository.transaction(
            operation="delete-database",
            resource_key=key,
        ) as state:
            database(state, catalog_id, normalized)
            state.databases.pop(key)
            for table_key in [value for value in state.tables if value[:2] == key]:
                state.tables.pop(table_key)
            for partition_key in [value for value in state.partitions if value[:2] == key]:
                state.partitions.pop(partition_key)


class DatabaseQueries:
    def __init__(self, repository: CatalogRepository, paginator: Paginator) -> None:
        self._repository = repository
        self._paginator = paginator

    async def get(self, catalog_id: str, database_name: str) -> CatalogDatabase:
        normalized = name(database_name)
        state = await self._repository.snapshot()
        return database(state, catalog_id, normalized)

    async def list(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]:
        state = await self._repository.snapshot()
        values = sorted(
            [value for key, value in state.databases.items() if key[0] == catalog_id],
            key=lambda item: item.name,
        )
        return self._paginator.page(values, next_token, max_results)
