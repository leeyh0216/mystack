"""Glue Data Catalog use cases and documented semantic invariants.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
"""

from __future__ import annotations

import base64
import binascii
import copy
import re
from dataclasses import dataclass
from typing import TypeVar

from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    InvalidInputError,
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
        except EntityNotFoundError:
            await self.create_database(self._policy.default_catalog_id, {"Name": "default"})

    async def create_database(self, catalog_id: str, definition: dict) -> CatalogDatabase:
        value = copy.deepcopy(definition)
        name = _required_name(value, "DatabaseInput.Name")
        value["Name"] = name
        database = CatalogDatabase(catalog_id, name, value, self._clock.now())
        await self._repository.create_database(database)
        return database

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase:
        return await self._repository.get_database(catalog_id, _name(name))

    async def get_databases(
        self,
        catalog_id: str,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogDatabase], str | None]:
        values = sorted(
            await self._repository.list_databases(catalog_id), key=lambda item: item.name
        )
        return self._page(values, next_token, max_results)

    async def update_database(
        self,
        catalog_id: str,
        old_name: str,
        definition: dict,
    ) -> None:
        current = await self.get_database(catalog_id, old_name)
        value = copy.deepcopy(definition)
        new_name = _required_name(value, "DatabaseInput.Name")
        value["Name"] = new_name
        await self._repository.update_database(
            current.name,
            CatalogDatabase(catalog_id, new_name, value, current.create_time),
        )

    async def delete_database(self, catalog_id: str, name: str) -> None:
        await self._repository.delete_database(catalog_id, _name(name))

    async def create_table(
        self,
        catalog_id: str,
        database_name: str,
        definition: dict,
    ) -> CatalogTable:
        database = await self.get_database(catalog_id, database_name)
        value = copy.deepcopy(definition)
        name = _required_name(value, "TableInput.Name")
        value["Name"] = name
        now = self._clock.now()
        table = CatalogTable(
            catalog_id,
            database.name,
            name,
            value,
            now,
            now,
            "0",
        )
        await self._repository.create_table(table)
        return table

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable:
        return await self._repository.get_table(catalog_id, _name(database), _name(name))

    async def get_tables(
        self,
        catalog_id: str,
        database: str,
        *,
        expression: str | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogTable], str | None]:
        await self.get_database(catalog_id, database)
        values = sorted(
            await self._repository.list_tables(catalog_id, _name(database)),
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
        current = await self.get_table(catalog_id, database, old_name)
        value = copy.deepcopy(definition)
        new_name = _required_name(value, "TableInput.Name")
        value["Name"] = new_name
        updated = CatalogTable(
            catalog_id=current.catalog_id,
            database_name=current.database_name,
            name=new_name,
            definition=value,
            create_time=current.create_time,
            update_time=self._clock.now(),
            version_id=str(int(current.version_id) + 1),
            archived_versions=current.archived_versions,
        )
        await self._repository.update_table(
            current.name,
            updated,
            expected_version_id=version_id,
            skip_archive=skip_archive,
        )

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None:
        await self._repository.delete_table(catalog_id, _name(database), _name(name))

    async def get_table_version(
        self,
        catalog_id: str,
        database: str,
        table: str,
        version_id: str | None,
    ) -> CatalogTableVersion:
        return await self._repository.get_table_version(
            catalog_id,
            _name(database),
            _name(table),
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
        values = await self._repository.list_table_versions(
            catalog_id,
            _name(database),
            _name(table),
        )
        return self._page(values, next_token, max_results)

    async def create_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        definition: dict,
    ) -> CatalogPartition:
        catalog_table = await self.get_table(catalog_id, database, table)
        value = copy.deepcopy(definition)
        values = tuple(map(str, value.get("Values", ())))
        self._validate_partition_values(catalog_table, values)
        value["Values"] = list(values)
        now = self._clock.now()
        partition = CatalogPartition(
            catalog_id,
            catalog_table.database_name,
            catalog_table.name,
            values,
            value,
            now,
            now,
        )
        await self._repository.create_partition(partition)
        return partition

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        await self.get_table(catalog_id, database, table)
        return await self._repository.get_partition(
            catalog_id,
            _name(database),
            _name(table),
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
        catalog_table = await self.get_table(catalog_id, database, table)
        partition_keys = [
            str(value.get("Name", ""))
            for value in catalog_table.definition.get("PartitionKeys", ())
        ]
        values = sorted(
            await self._repository.list_partitions(catalog_id, _name(database), _name(table)),
            key=lambda item: item.values,
        )
        values = [
            partition
            for partition in values
            if matches_partition(
                expression, dict(zip(partition_keys, partition.values, strict=True))
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
        current = await self.get_partition(catalog_id, database, table, old_values)
        catalog_table = await self.get_table(catalog_id, database, table)
        value = copy.deepcopy(definition)
        new_values = tuple(map(str, value.get("Values", ())))
        self._validate_partition_values(catalog_table, new_values)
        value["Values"] = list(new_values)
        await self._repository.update_partition(
            current.values,
            CatalogPartition(
                current.catalog_id,
                current.database_name,
                current.table_name,
                new_values,
                value,
                current.creation_time,
                self._clock.now(),
            ),
        )

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None:
        await self._repository.delete_partition(
            catalog_id,
            _name(database),
            _name(table),
            values,
        )

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
