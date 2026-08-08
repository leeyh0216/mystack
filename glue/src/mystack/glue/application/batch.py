"""Partial-success Glue partition batch use cases.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchCreatePartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchGetPartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchUpdatePartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchDeletePartition.html
"""

from __future__ import annotations

from dataclasses import dataclass

from mystack.glue.application.partition import PartitionCommands, PartitionQueries
from mystack.glue.domain import CatalogPartition, EntityNotFoundError
from mystack.glue.domain.errors import GlueDomainError


@dataclass(frozen=True, slots=True)
class PartitionBatchFailure:
    values: tuple[str, ...]
    error: GlueDomainError


class PartitionBatchHandler:
    def __init__(
        self,
        commands: PartitionCommands,
        queries: PartitionQueries,
    ) -> None:
        self._commands = commands
        self._queries = queries

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        definitions: list[dict],
    ) -> list[PartitionBatchFailure]:
        failures: list[PartitionBatchFailure] = []
        for definition in definitions:
            values = tuple(map(str, definition.get("Values", ())))
            try:
                await self._commands.create(
                    catalog_id,
                    database_name,
                    table_name,
                    definition,
                )
            except GlueDomainError as error:
                failures.append(PartitionBatchFailure(values, error))
        return failures

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[CatalogPartition]:
        partitions: list[CatalogPartition] = []
        for values in value_groups:
            try:
                value = await self._queries.get(
                    catalog_id,
                    database_name,
                    table_name,
                    values,
                )
            except EntityNotFoundError:
                continue
            partitions.append(value)
        return partitions

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        entries: list[tuple[tuple[str, ...], dict]],
    ) -> list[PartitionBatchFailure]:
        failures: list[PartitionBatchFailure] = []
        for old_values, definition in entries:
            try:
                await self._commands.update(
                    catalog_id,
                    database_name,
                    table_name,
                    old_values,
                    definition,
                )
            except GlueDomainError as error:
                failures.append(PartitionBatchFailure(old_values, error))
        return failures

    async def delete(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[PartitionBatchFailure]:
        failures: list[PartitionBatchFailure] = []
        for values in value_groups:
            try:
                await self._commands.delete(
                    catalog_id,
                    database_name,
                    table_name,
                    values,
                )
            except GlueDomainError as error:
                failures.append(PartitionBatchFailure(values, error))
        return failures
