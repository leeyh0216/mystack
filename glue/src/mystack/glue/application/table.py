"""Focused Glue table command, query, and version handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
"""

from __future__ import annotations

import copy
import re

from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    InvalidInputError,
)
from mystack.glue.domain.repositories import CatalogRepository

from .pagination import Paginator
from .ports import Clock
from .state import database, name, rename_table_partitions, table


class TableCommands:
    def __init__(self, repository: CatalogRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        definition: dict,
    ) -> CatalogTable:
        normalized_database = name(database_name)
        value = CatalogTable.create(
            catalog_id,
            normalized_database,
            definition,
            self._clock.now(),
        )
        key = (catalog_id, normalized_database, value.name)
        async with self._repository.transaction(
            operation="create-table",
            resource_key=key,
        ) as state:
            database(state, catalog_id, normalized_database)
            if key in state.tables:
                raise AlreadyExistsError(f"Table {normalized_database}.{value.name} already exists")
            state.tables[key] = copy.deepcopy(value)
        return value

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        old_name: str,
        definition: dict,
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None:
        normalized_database = name(database_name)
        normalized_old = name(old_name)
        old_key = (catalog_id, normalized_database, normalized_old)
        async with self._repository.transaction(
            operation="update-table",
            resource_key=old_key,
        ) as state:
            current = table(state, catalog_id, normalized_database, normalized_old)
            revised = current.revise(
                definition,
                now=self._clock.now(),
                expected_version_id=version_id,
                skip_archive=skip_archive,
            )
            new_key = (catalog_id, normalized_database, revised.name)
            if new_key != old_key and new_key in state.tables:
                raise AlreadyExistsError(
                    f"Table {normalized_database}.{revised.name} already exists"
                )
            state.tables.pop(old_key)
            state.tables[new_key] = revised
            if new_key != old_key:
                rename_table_partitions(
                    state,
                    catalog_id,
                    normalized_database,
                    normalized_old,
                    revised.name,
                )

    async def delete(self, catalog_id: str, database_name: str, table_name: str) -> None:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        key = (catalog_id, normalized_database, normalized_table)
        async with self._repository.transaction(
            operation="delete-table",
            resource_key=key,
        ) as state:
            table(state, catalog_id, normalized_database, normalized_table)
            state.tables.pop(key)
            for partition_key in [value for value in state.partitions if value[:3] == key]:
                state.partitions.pop(partition_key)


class TableQueries:
    def __init__(self, repository: CatalogRepository, paginator: Paginator) -> None:
        self._repository = repository
        self._paginator = paginator

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogTable:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        state = await self._repository.snapshot()
        return table(state, catalog_id, normalized_database, normalized_table)

    async def list(
        self,
        catalog_id: str,
        database_name: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]:
        normalized_database = name(database_name)
        state = await self._repository.snapshot()
        database(state, catalog_id, normalized_database)
        values = sorted(
            [
                value
                for key, value in state.tables.items()
                if key[:2] == (catalog_id, normalized_database)
            ],
            key=lambda item: item.name,
        )
        if expression:
            try:
                pattern = re.compile(expression)
            except re.error as error:
                raise InvalidInputError(f"Invalid table expression: {error}") from error
            values = [value for value in values if pattern.search(value.name)]
        return self._paginator.page(values, next_token, max_results)


class TableVersionQueries:
    def __init__(self, tables: TableQueries, paginator: Paginator) -> None:
        self._tables = tables
        self._paginator = paginator

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        version_id: str | None,
    ) -> CatalogTableVersion:
        current = await self._tables.get(catalog_id, database_name, table_name)
        versions = current.versions()
        if version_id is None:
            return versions[-1]
        for value in versions:
            if value.version_id == version_id:
                return value
        raise EntityNotFoundError(
            f"Table version {name(database_name)}.{name(table_name)}@{version_id} does not exist"
        )

    async def list(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTableVersion], str | None]:
        current = await self._tables.get(catalog_id, database_name, table_name)
        return self._paginator.page(list(current.versions()), next_token, max_results)
