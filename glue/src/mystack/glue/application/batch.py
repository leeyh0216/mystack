"""Partial-success Glue partition batch use cases.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchCreatePartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchGetPartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchUpdatePartition.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_BatchDeletePartition.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.partition import (
    PartitionCommands,
    PartitionQueries,
    PartitionTargetResolver,
)
from mystack.glue.domain import CatalogPartition, EntityNotFoundError, PartitionValues
from mystack.glue.domain.errors import GlueDomainError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PartitionBatchFailure:
    values: tuple[str, ...]
    error: GlueDomainError


@dataclass(frozen=True, slots=True)
class PartitionBatchGetResult:
    partitions: tuple[CatalogPartition, ...]
    unprocessed_keys: tuple[tuple[str, ...], ...]


class PartitionBatchHandler:
    def __init__(
        self,
        commands: PartitionCommands,
        queries: PartitionQueries,
        targets: PartitionTargetResolver,
    ) -> None:
        self._commands = commands
        self._queries = queries
        self._targets = targets

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        definitions: list[dict],
    ) -> list[PartitionBatchFailure]:
        operation = "BatchCreatePartition"
        self._log_before(operation, len(definitions))
        await self._targets.require(catalog_id, database_name, table_name)
        failures: list[PartitionBatchFailure] = []
        for item_index, definition in enumerate(definitions):
            values = tuple(map(str, definition.get("Values", ())))
            try:
                await self._commands.create(
                    catalog_id,
                    database_name,
                    table_name,
                    definition,
                )
            except GlueDomainError as error:
                self._log_item_failure(operation, item_index, error)
                failures.append(PartitionBatchFailure(values, error))
        self._log_after(operation, len(definitions), len(failures))
        return failures

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        value_groups: list[tuple[str, ...]],
    ) -> PartitionBatchGetResult:
        operation = "BatchGetPartition"
        self._log_before(operation, len(value_groups))
        target = await self._targets.require(catalog_id, database_name, table_name)
        normalized_groups = [
            PartitionValues.from_items(
                values,
                expected_count=target.expected_value_count,
            ).items
            for values in value_groups
        ]
        partitions: list[CatalogPartition] = []
        unprocessed: list[tuple[str, ...]] = []
        for values in normalized_groups:
            try:
                value = await self._queries.get(
                    catalog_id,
                    database_name,
                    table_name,
                    values,
                )
            except EntityNotFoundError:
                unprocessed.append(values)
                continue
            partitions.append(value)
        self._log_after(
            operation,
            len(normalized_groups),
            len(unprocessed),
            success_count=len(partitions),
            unprocessed_count=len(unprocessed),
        )
        return PartitionBatchGetResult(tuple(partitions), tuple(unprocessed))

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        entries: list[tuple[tuple[str, ...], dict]],
    ) -> list[PartitionBatchFailure]:
        operation = "BatchUpdatePartition"
        self._log_before(operation, len(entries))
        await self._targets.require(catalog_id, database_name, table_name)
        failures: list[PartitionBatchFailure] = []
        for item_index, (old_values, definition) in enumerate(entries):
            try:
                await self._commands.update(
                    catalog_id,
                    database_name,
                    table_name,
                    old_values,
                    definition,
                )
            except GlueDomainError as error:
                self._log_item_failure(operation, item_index, error)
                failures.append(PartitionBatchFailure(old_values, error))
        self._log_after(operation, len(entries), len(failures))
        return failures

    async def delete(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        value_groups: list[tuple[str, ...]],
    ) -> list[PartitionBatchFailure]:
        operation = "BatchDeletePartition"
        self._log_before(operation, len(value_groups))
        await self._targets.require(catalog_id, database_name, table_name)
        failures: list[PartitionBatchFailure] = []
        for item_index, values in enumerate(value_groups):
            try:
                await self._commands.delete(
                    catalog_id,
                    database_name,
                    table_name,
                    values,
                )
            except GlueDomainError as error:
                self._log_item_failure(operation, item_index, error)
                failures.append(PartitionBatchFailure(values, error))
        self._log_after(operation, len(value_groups), len(failures))
        return failures

    @staticmethod
    def _log_before(operation: str, item_count: int) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_batch.before",
            operation=operation,
            item_count=item_count,
            fix_hint=(
                "If a client upgrade changes batch inputs, inspect aws_batch.py; if ordering or "
                "partial success changes, inspect application/batch.py."
            ),
        )

    @staticmethod
    def _log_item_failure(
        operation: str,
        item_index: int,
        error: GlueDomainError,
    ) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_batch.item.failed",
            operation=operation,
            item_index=item_index,
            failure_type=type(error).__name__,
            fix_hint=(
                "Compare this item invariant with the partition/batch error protocol and the "
                "machine-readable Glue error catalog."
            ),
        )

    @staticmethod
    def _log_after(
        operation: str,
        item_count: int,
        failure_count: int,
        *,
        success_count: int | None = None,
        unprocessed_count: int = 0,
    ) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_batch.after",
            operation=operation,
            item_count=item_count,
            success_count=(item_count - failure_count if success_count is None else success_count),
            failure_count=failure_count,
            unprocessed_count=unprocessed_count,
        )
