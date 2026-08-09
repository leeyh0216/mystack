"""Focused Glue table command, query, and version handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
"""

from __future__ import annotations

import re

from mystack.glue.application.catalog_identity import database, name, table
from mystack.glue.application.catalog_ports import CatalogReadPort, CatalogWritePort
from mystack.glue.application.iceberg_commit import IcebergCommitObserver
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.ports import Clock
from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)


class TableCommands:
    def __init__(
        self,
        catalog: CatalogWritePort,
        clock: Clock,
        iceberg_commits: IcebergCommitObserver,
    ) -> None:
        self._catalog = catalog
        self._clock = clock
        self._iceberg_commits = iceberg_commits

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
        async with self._catalog.transaction(
            operation="create-table",
            resource_key=key,
        ) as transaction:
            await database(transaction, catalog_id, normalized_database)
            if (
                await transaction.find_table(catalog_id, normalized_database, value.name)
                is not None
            ):
                raise AlreadyExistsError(f"Table {normalized_database}.{value.name} already exists")
            if not await transaction.insert_table(value):
                raise AlreadyExistsError(f"Table {normalized_database}.{value.name} already exists")
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
        revised_name = CatalogTable.definition_name(definition)
        if version_id is not None:
            version_id = CatalogTableVersion.validated_id(version_id)
        old_key = (catalog_id, normalized_database, normalized_old)
        attempt = None
        try:
            async with self._catalog.transaction(
                operation="update-table",
                resource_key=old_key,
            ) as transaction:
                current = await table(transaction, catalog_id, normalized_database, normalized_old)
                attempt = self._iceberg_commits.begin(
                    current,
                    definition,
                    expected_version_id=version_id,
                    skip_archive=skip_archive,
                )
                new_key = (catalog_id, normalized_database, revised_name)
                if (
                    new_key != old_key
                    and await transaction.find_table(catalog_id, normalized_database, revised_name)
                    is not None
                ):
                    raise AlreadyExistsError(
                        f"Table {normalized_database}.{revised_name} already exists"
                    )
                try:
                    revised = current.revise(
                        definition,
                        now=self._clock.now(),
                        expected_version_id=version_id,
                        skip_archive=skip_archive,
                    )
                except VersionMismatchError:
                    if attempt is not None:
                        attempt.conflicted()
                    raise
                if attempt is not None:
                    attempt.accepted(revised.version_id)
                if new_key != old_key:
                    for optimizer in await transaction.list_optimizers_for_table(
                        catalog_id,
                        normalized_database,
                        normalized_old,
                    ):
                        if optimizer.active_run is None:
                            continue
                        cancelled = optimizer.cancel_active_run(
                            now=self._clock.now(),
                            reason="Owning Glue table was renamed during optimizer execution",
                        )
                        if not await transaction.replace_optimizer(optimizer, cancelled):
                            raise RuntimeError(
                                "SQLite catalog optimizer changed during table rename"
                            )
                if not await transaction.replace_table(current, revised):
                    if version_id is not None:
                        if attempt is not None:
                            attempt.conflicted()
                        raise VersionMismatchError(
                            f"Expected table version {version_id}, current version changed"
                        )
                    raise RuntimeError("SQLite catalog table changed during update")
                if attempt is not None:
                    attempt.persisting(revised.version_id)
        except VersionMismatchError:
            raise
        except BaseException as error:
            if attempt is not None:
                attempt.failed(error)
            raise
        if attempt is not None:
            attempt.succeeded(revised.version_id)

    async def delete(self, catalog_id: str, database_name: str, table_name: str) -> None:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        key = (catalog_id, normalized_database, normalized_table)
        async with self._catalog.transaction(
            operation="delete-table",
            resource_key=key,
        ) as transaction:
            current = await table(transaction, catalog_id, normalized_database, normalized_table)
            if not await transaction.delete_table(current):
                raise RuntimeError("SQLite catalog table changed during delete")


class TableQueries:
    def __init__(self, catalog: CatalogReadPort, paginator: Paginator) -> None:
        self._catalog = catalog
        self._paginator = paginator

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogTable:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        return await table(self._catalog, catalog_id, normalized_database, normalized_table)

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
        page_request = self._paginator.prepare(next_token, max_results)
        pattern = None
        if expression:
            try:
                pattern = re.compile(expression)
            except re.error as error:
                raise InvalidInputError(f"Invalid table expression: {error}") from error
        await database(self._catalog, catalog_id, normalized_database)
        values = list(await self._catalog.list_tables(catalog_id, normalized_database))
        if pattern is not None:
            values = [value for value in values if pattern.search(value.name)]
        return page_request.apply(values)


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
        if version_id is not None:
            version_id = CatalogTableVersion.validated_id(version_id)
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
        page_request = self._paginator.prepare(next_token, max_results)
        current = await self._tables.get(catalog_id, database_name, table_name)
        return page_request.apply(list(current.versions()))
