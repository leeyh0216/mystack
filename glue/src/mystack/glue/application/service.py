"""Glue Data Catalog use cases and transactional semantic invariants.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
"""

from __future__ import annotations

import base64
import binascii
import copy
import re
from dataclasses import dataclass
from typing import TypeVar

from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogDatabase,
    CatalogPartition,
    CatalogState,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)
from mystack.glue.domain.repositories import CatalogRepository

from .expression import matches_partition
from .ports import Clock

_Item = TypeVar("_Item")


@dataclass(frozen=True, slots=True)
class CatalogPolicy:
    default_catalog_id: str
    api_page_size: int
    create_default_database: bool


class CatalogApplication:
    def __init__(
        self,
        repository: CatalogRepository,
        clock: Clock,
        policy: CatalogPolicy,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._policy = policy

    async def initialize(self) -> None:
        if not self._policy.create_default_database:
            return
        try:
            await self.get_database(self._policy.default_catalog_id, "default")
            return
        except EntityNotFoundError:
            try:
                await self.create_database(
                    self._policy.default_catalog_id,
                    {"Name": "default"},
                )
            except AlreadyExistsError:
                pass

    async def create_database(self, catalog_id: str, definition: dict) -> CatalogDatabase:
        value = copy.deepcopy(definition)
        name = _required_name(value, "DatabaseInput.Name")
        value["Name"] = name
        database = CatalogDatabase(catalog_id, name, value, self._clock.now())
        key = (catalog_id, name)
        async with self._repository.transaction(
            operation="create-database",
            resource_key=key,
        ) as state:
            if key in state.databases:
                raise AlreadyExistsError(f"Database {name!r} already exists")
            state.databases[key] = copy.deepcopy(database)
        return database

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase:
        normalized = _name(name)
        state = await self._repository.snapshot()
        return _database(state, catalog_id, normalized)

    async def get_databases(
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
        return self._page(values, next_token, max_results)

    async def update_database(
        self,
        catalog_id: str,
        old_name: str,
        definition: dict,
    ) -> None:
        normalized_old = _name(old_name)
        value = copy.deepcopy(definition)
        new_name = _required_name(value, "DatabaseInput.Name")
        value["Name"] = new_name
        old_key = (catalog_id, normalized_old)
        new_key = (catalog_id, new_name)
        async with self._repository.transaction(
            operation="update-database",
            resource_key=old_key,
        ) as state:
            current = _database(state, catalog_id, normalized_old)
            if new_key != old_key and new_key in state.databases:
                raise AlreadyExistsError(f"Database {new_name!r} already exists")
            state.databases.pop(old_key)
            state.databases[new_key] = CatalogDatabase(
                catalog_id,
                new_name,
                value,
                current.create_time,
            )
            if new_key != old_key:
                _rename_database_children(state, catalog_id, normalized_old, new_name)

    async def delete_database(self, catalog_id: str, name: str) -> None:
        normalized = _name(name)
        key = (catalog_id, normalized)
        async with self._repository.transaction(
            operation="delete-database",
            resource_key=key,
        ) as state:
            _database(state, catalog_id, normalized)
            state.databases.pop(key)
            for table_key in [value for value in state.tables if value[:2] == key]:
                state.tables.pop(table_key)
            for partition_key in [value for value in state.partitions if value[:2] == key]:
                state.partitions.pop(partition_key)

    async def create_table(
        self,
        catalog_id: str,
        database_name: str,
        definition: dict,
    ) -> CatalogTable:
        normalized_database = _name(database_name)
        value = copy.deepcopy(definition)
        name = _required_name(value, "TableInput.Name")
        value["Name"] = name
        now = self._clock.now()
        table = CatalogTable(
            catalog_id,
            normalized_database,
            name,
            value,
            now,
            now,
            "0",
        )
        key = (catalog_id, normalized_database, name)
        async with self._repository.transaction(
            operation="create-table",
            resource_key=key,
        ) as state:
            database = _database(state, catalog_id, normalized_database)
            table.database_name = database.name
            if key in state.tables:
                raise AlreadyExistsError(f"Table {normalized_database}.{name} already exists")
            state.tables[key] = copy.deepcopy(table)
        return table

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable:
        normalized_database = _name(database)
        normalized_name = _name(name)
        state = await self._repository.snapshot()
        return _table(state, catalog_id, normalized_database, normalized_name)

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]:
        normalized_database = _name(database)
        state = await self._repository.snapshot()
        _database(state, catalog_id, normalized_database)
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
        return self._page(values, next_token, max_results)

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
        normalized_database = _name(database)
        normalized_old = _name(old_name)
        value = copy.deepcopy(definition)
        new_name = _required_name(value, "TableInput.Name")
        value["Name"] = new_name
        old_key = (catalog_id, normalized_database, normalized_old)
        new_key = (catalog_id, normalized_database, new_name)
        async with self._repository.transaction(
            operation="update-table",
            resource_key=old_key,
        ) as state:
            current = _table(state, catalog_id, normalized_database, normalized_old)
            if version_id is not None and current.version_id != version_id:
                raise VersionMismatchError(
                    f"Expected table version {version_id}, current version is {current.version_id}"
                )
            if new_key != old_key and new_key in state.tables:
                raise AlreadyExistsError(f"Table {normalized_database}.{new_name} already exists")
            archived = copy.deepcopy(current.archived_versions)
            if not skip_archive:
                archived.append(_version(current))
            updated = CatalogTable(
                catalog_id=current.catalog_id,
                database_name=current.database_name,
                name=new_name,
                definition=value,
                create_time=current.create_time,
                update_time=self._clock.now(),
                version_id=str(int(current.version_id) + 1),
                archived_versions=archived,
            )
            state.tables.pop(old_key)
            state.tables[new_key] = updated
            if new_key != old_key:
                _rename_table_partitions(
                    state,
                    catalog_id,
                    normalized_database,
                    normalized_old,
                    new_name,
                )

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None:
        normalized_database = _name(database)
        normalized_name = _name(name)
        key = (catalog_id, normalized_database, normalized_name)
        async with self._repository.transaction(
            operation="delete-table",
            resource_key=key,
        ) as state:
            _table(state, catalog_id, normalized_database, normalized_name)
            state.tables.pop(key)
            for partition_key in [value for value in state.partitions if value[:3] == key]:
                state.partitions.pop(partition_key)

    async def get_table_version(
        self,
        catalog_id: str,
        database: str,
        table: str,
        version_id: str | None,
    ) -> CatalogTableVersion:
        current = await self.get_table(catalog_id, database, table)
        versions = [*current.archived_versions, _version(current)]
        if version_id is None:
            return versions[-1]
        for value in versions:
            if value.version_id == version_id:
                return value
        raise EntityNotFoundError(
            f"Table version {_name(database)}.{_name(table)}@{version_id} does not exist"
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
        current = await self.get_table(catalog_id, database, table)
        values = [*current.archived_versions, _version(current)]
        return self._page(values, next_token, max_results)

    async def create_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definition: dict,
    ) -> CatalogPartition:
        normalized_database = _name(database)
        normalized_table = _name(table)
        value = copy.deepcopy(definition)
        values = tuple(map(str, value.get("Values", ())))
        value["Values"] = list(values)
        now = self._clock.now()
        partition = CatalogPartition(
            catalog_id,
            normalized_database,
            normalized_table,
            values,
            value,
            now,
            now,
        )
        key = _partition_key(partition)
        async with self._repository.transaction(
            operation="create-partition",
            resource_key=key,
        ) as state:
            catalog_table = _table(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
            )
            self._validate_partition_values(catalog_table, values)
            if key in state.partitions:
                raise AlreadyExistsError(f"Partition {list(values)!r} already exists")
            state.partitions[key] = copy.deepcopy(partition)
        return partition

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        normalized_database = _name(database)
        normalized_table = _name(table)
        state = await self._repository.snapshot()
        _table(state, catalog_id, normalized_database, normalized_table)
        return _partition(state, catalog_id, normalized_database, normalized_table, values)

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
        normalized_database = _name(database)
        normalized_table = _name(table)
        state = await self._repository.snapshot()
        catalog_table = _table(
            state,
            catalog_id,
            normalized_database,
            normalized_table,
        )
        partition_keys = [
            str(value.get("Name", ""))
            for value in catalog_table.definition.get("PartitionKeys", ())
        ]
        prefix = (catalog_id, normalized_database, normalized_table)
        values = sorted(
            [value for key, value in state.partitions.items() if key[:3] == prefix],
            key=lambda item: item.values,
        )
        values = [
            partition
            for partition in values
            if matches_partition(
                expression,
                dict(zip(partition_keys, partition.values, strict=True)),
            )
        ]
        if segment is not None:
            segment_number, total_segments = segment
            if total_segments <= 0 or not 0 <= segment_number < total_segments:
                raise InvalidInputError("SegmentNumber must be in [0, TotalSegments)")
            values = [
                value
                for value in values
                if _stable_segment(value.values, total_segments) == segment_number
            ]
        return self._page(values, next_token, max_results)

    async def update_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        old_values: tuple[str, ...],
        definition: dict,
    ) -> None:
        normalized_database = _name(database)
        normalized_table = _name(table)
        value = copy.deepcopy(definition)
        new_values = tuple(map(str, value.get("Values", ())))
        value["Values"] = list(new_values)
        old_key = (catalog_id, normalized_database, normalized_table, old_values)
        new_key = (catalog_id, normalized_database, normalized_table, new_values)
        async with self._repository.transaction(
            operation="update-partition",
            resource_key=old_key,
        ) as state:
            current = _partition(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
                old_values,
            )
            catalog_table = _table(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
            )
            self._validate_partition_values(catalog_table, new_values)
            if new_key != old_key and new_key in state.partitions:
                raise AlreadyExistsError(f"Partition {list(new_values)!r} already exists")
            state.partitions.pop(old_key)
            state.partitions[new_key] = CatalogPartition(
                current.catalog_id,
                current.database_name,
                current.table_name,
                new_values,
                value,
                current.creation_time,
                self._clock.now(),
            )

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None:
        normalized_database = _name(database)
        normalized_table = _name(table)
        key = (catalog_id, normalized_database, normalized_table, values)
        async with self._repository.transaction(
            operation="delete-partition",
            resource_key=key,
        ) as state:
            _partition(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
                values,
            )
            state.partitions.pop(key)

    def _page(
        self,
        values: list[_Item],
        token: str | None,
        max_results: int | None,
    ) -> tuple[list[_Item], str | None]:
        offset = _decode_token(token)
        size = min(max_results or self._policy.api_page_size, self._policy.api_page_size)
        if size <= 0:
            raise InvalidInputError("MaxResults must be positive")
        page = values[offset : offset + size]
        next_offset = offset + len(page)
        return page, _encode_token(next_offset) if next_offset < len(values) else None

    @staticmethod
    def _validate_partition_values(table: CatalogTable, values: tuple[str, ...]) -> None:
        expected = len(table.definition.get("PartitionKeys", ()))
        if len(values) != expected:
            raise InvalidInputError(
                f"Partition has {len(values)} values but table requires {expected}"
            )


def _database(state: CatalogState, catalog_id: str, name: str) -> CatalogDatabase:
    value = state.databases.get((catalog_id, name))
    if value is None:
        raise EntityNotFoundError(f"Database {name!r} does not exist")
    return value


def _table(state: CatalogState, catalog_id: str, database: str, name: str) -> CatalogTable:
    value = state.tables.get((catalog_id, database, name))
    if value is None:
        raise EntityNotFoundError(f"Table {database}.{name} does not exist")
    return value


def _partition(
    state: CatalogState,
    catalog_id: str,
    database: str,
    table: str,
    values: tuple[str, ...],
) -> CatalogPartition:
    value = state.partitions.get((catalog_id, database, table, values))
    if value is None:
        raise EntityNotFoundError(f"Partition {list(values)!r} does not exist")
    return value


def _rename_database_children(
    state: CatalogState,
    catalog_id: str,
    old: str,
    new: str,
) -> None:
    for key in [value for value in state.tables if value[:2] == (catalog_id, old)]:
        table = state.tables.pop(key)
        table.database_name = new
        state.tables[(catalog_id, new, table.name)] = table
    for key in [value for value in state.partitions if value[:2] == (catalog_id, old)]:
        partition = state.partitions.pop(key)
        partition.database_name = new
        state.partitions[_partition_key(partition)] = partition


def _rename_table_partitions(
    state: CatalogState,
    catalog_id: str,
    database: str,
    old: str,
    new: str,
) -> None:
    prefix = (catalog_id, database, old)
    for key in [value for value in state.partitions if value[:3] == prefix]:
        partition = state.partitions.pop(key)
        partition.table_name = new
        state.partitions[_partition_key(partition)] = partition


def _partition_key(partition: CatalogPartition) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        partition.catalog_id,
        partition.database_name,
        partition.table_name,
        partition.values,
    )


def _version(table: CatalogTable) -> CatalogTableVersion:
    return CatalogTableVersion(
        version_id=table.version_id,
        definition=copy.deepcopy(table.definition),
        create_time=table.create_time,
        update_time=table.update_time,
    )


def _name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidInputError("Catalog names cannot be empty")
    return stripped.lower()


def _required_name(definition: dict, path: str) -> str:
    if "Name" not in definition:
        raise InvalidInputError(f"{path} is required")
    return _name(str(definition["Name"]))


def _stable_segment(values: tuple[str, ...], total_segments: int) -> int:
    import hashlib

    digest = hashlib.sha256("\0".join(values).encode()).digest()
    return int.from_bytes(digest[:8], "big") % total_segments


def _encode_token(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_token(token: str | None) -> int:
    if not token:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(token.encode()).decode())
        if value < 0:
            raise ValueError
        return value
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidInputError("Invalid pagination token") from error
