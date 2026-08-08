"""Focused Glue partition command and query handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
"""

from __future__ import annotations

import hashlib

from mystack.glue.application.expression import matches_partition
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.ports import Clock
from mystack.glue.application.state import name, partition, partition_key, table
from mystack.glue.domain import AlreadyExistsError, CatalogPartition, InvalidInputError
from mystack.glue.domain.repositories import CatalogRepository


class PartitionCommands:
    def __init__(self, repository: CatalogRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        definition: dict,
    ) -> CatalogPartition:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        resource_key = (catalog_id, normalized_database, normalized_table)
        async with self._repository.transaction(
            operation="create-partition",
            resource_key=resource_key,
        ) as state:
            parent = table(state, catalog_id, normalized_database, normalized_table)
            value = CatalogPartition.create(
                catalog_id,
                normalized_database,
                normalized_table,
                definition,
                expected_value_count=parent.partition_key_count(),
                now=self._clock.now(),
            )
            key = partition_key(value)
            if key in state.partitions:
                raise AlreadyExistsError(f"Partition {list(value.values)!r} already exists")
            state.partitions[key] = value
        return value

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        old_values: tuple[str, ...],
        definition: dict,
    ) -> None:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        old_key = (catalog_id, normalized_database, normalized_table, old_values)
        async with self._repository.transaction(
            operation="update-partition",
            resource_key=old_key,
        ) as state:
            current = partition(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
                old_values,
            )
            parent = table(state, catalog_id, normalized_database, normalized_table)
            revised = current.revise(
                definition,
                expected_value_count=parent.partition_key_count(),
                now=self._clock.now(),
            )
            new_key = partition_key(revised)
            if new_key != old_key and new_key in state.partitions:
                raise AlreadyExistsError(f"Partition {list(revised.values)!r} already exists")
            state.partitions.pop(old_key)
            state.partitions[new_key] = revised

    async def delete(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> None:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        key = (catalog_id, normalized_database, normalized_table, values)
        async with self._repository.transaction(
            operation="delete-partition",
            resource_key=key,
        ) as state:
            partition(
                state,
                catalog_id,
                normalized_database,
                normalized_table,
                values,
            )
            state.partitions.pop(key)


class PartitionQueries:
    def __init__(self, repository: CatalogRepository, paginator: Paginator) -> None:
        self._repository = repository
        self._paginator = paginator

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        state = await self._repository.snapshot()
        table(state, catalog_id, normalized_database, normalized_table)
        return partition(
            state,
            catalog_id,
            normalized_database,
            normalized_table,
            values,
        )

    async def list(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        *,
        expression: str | None,
        segment: tuple[int, int] | None,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[CatalogPartition], str | None]:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        state = await self._repository.snapshot()
        parent = table(state, catalog_id, normalized_database, normalized_table)
        partition_keys = [
            str(value.get("Name", "")) for value in parent.definition.get("PartitionKeys", ())
        ]
        prefix = (catalog_id, normalized_database, normalized_table)
        values = sorted(
            [value for key, value in state.partitions.items() if key[:3] == prefix],
            key=lambda item: item.values,
        )
        values = [
            value
            for value in values
            if matches_partition(
                expression,
                dict(zip(partition_keys, value.values, strict=True)),
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
        return self._paginator.page(values, next_token, max_results)


def _stable_segment(values: tuple[str, ...], total_segments: int) -> int:
    digest = hashlib.sha256("\0".join(values).encode()).digest()
    return int.from_bytes(digest[:8], "big") % total_segments
