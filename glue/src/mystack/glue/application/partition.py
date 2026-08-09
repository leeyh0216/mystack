"""Focused Glue partition command and query handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.catalog_identity import name, partition, table
from mystack.glue.application.catalog_ports import CatalogReadPort, CatalogWritePort
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.partition_expression import (
    PartitionExpressionCompiler,
    PartitionKey,
)
from mystack.glue.application.ports import Clock
from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogPartition,
    InvalidInputError,
    PartitionValues,
)

_LOGGER = logging.getLogger(__name__)
_MAX_PARTITION_SEGMENTS = 10


@dataclass(frozen=True, slots=True)
class PartitionTarget:
    """Resolved parent facts needed by batch orchestration without exposing repository state."""

    expected_value_count: int


class PartitionTargetResolver:
    def __init__(self, catalog: CatalogReadPort) -> None:
        self._catalog = catalog

    async def require(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> PartitionTarget:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        parent = await table(self._catalog, catalog_id, normalized_database, normalized_table)
        return PartitionTarget(parent.partition_key_count())


@dataclass(frozen=True, slots=True)
class PartitionSegment:
    number: int
    total: int

    @classmethod
    def from_request(cls, value: tuple[int, int] | None) -> PartitionSegment | None:
        if value is None:
            return None
        number, total = value
        if total <= 0 or total > _MAX_PARTITION_SEGMENTS:
            raise InvalidInputError(
                f"TotalSegments must be between 1 and {_MAX_PARTITION_SEGMENTS}"
            )
        if not 0 <= number < total:
            raise InvalidInputError("SegmentNumber must be in [0, TotalSegments)")
        return cls(number, total)

    def includes(self, values: tuple[str, ...]) -> bool:
        return _stable_segment(values, self.total) == self.number


class PartitionCommands:
    def __init__(self, catalog: CatalogWritePort, clock: Clock) -> None:
        self._catalog = catalog
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
        async with self._catalog.transaction(
            operation="create-partition",
            resource_key=resource_key,
        ) as transaction:
            parent = await table(transaction, catalog_id, normalized_database, normalized_table)
            value = CatalogPartition.create(
                catalog_id,
                normalized_database,
                normalized_table,
                definition,
                expected_value_count=parent.partition_key_count(),
                now=self._clock.now(),
            )
            if (
                await transaction.find_partition(
                    catalog_id,
                    normalized_database,
                    normalized_table,
                    value.values,
                )
                is not None
            ):
                raise AlreadyExistsError(f"Partition {list(value.values)!r} already exists")
            if not await transaction.insert_partition(value):
                raise AlreadyExistsError(f"Partition {list(value.values)!r} already exists")
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
        async with self._catalog.transaction(
            operation="update-partition",
            resource_key=old_key,
        ) as transaction:
            parent = await table(transaction, catalog_id, normalized_database, normalized_table)
            normalized_old_values = PartitionValues.from_items(
                old_values,
                expected_count=parent.partition_key_count(),
            ).items
            old_key = (
                catalog_id,
                normalized_database,
                normalized_table,
                normalized_old_values,
            )
            current = await partition(
                transaction,
                catalog_id,
                normalized_database,
                normalized_table,
                normalized_old_values,
            )
            revised = current.revise(
                definition,
                expected_value_count=parent.partition_key_count(),
                now=self._clock.now(),
            )
            if (
                revised.values != normalized_old_values
                and await transaction.find_partition(
                    catalog_id,
                    normalized_database,
                    normalized_table,
                    revised.values,
                )
                is not None
            ):
                raise InvalidInputError(
                    f"Partition destination {list(revised.values)!r} already exists"
                )
            if not await transaction.replace_partition(current, revised):
                raise RuntimeError("SQLite catalog partition changed during update")

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
        async with self._catalog.transaction(
            operation="delete-partition",
            resource_key=key,
        ) as transaction:
            parent = await table(transaction, catalog_id, normalized_database, normalized_table)
            normalized_values = PartitionValues.from_items(
                values,
                expected_count=parent.partition_key_count(),
            ).items
            key = (catalog_id, normalized_database, normalized_table, normalized_values)
            current = await partition(
                transaction,
                catalog_id,
                normalized_database,
                normalized_table,
                normalized_values,
            )
            if not await transaction.delete_partition(current):
                raise RuntimeError("SQLite catalog partition changed during delete")


class PartitionQueries:
    def __init__(
        self,
        catalog: CatalogReadPort,
        paginator: Paginator,
        expression_compiler: PartitionExpressionCompiler,
    ) -> None:
        self._catalog = catalog
        self._paginator = paginator
        self._expression_compiler = expression_compiler

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        normalized_database = name(database_name)
        normalized_table = name(table_name)
        parent = await table(self._catalog, catalog_id, normalized_database, normalized_table)
        normalized_values = PartitionValues.from_items(
            values,
            expected_count=parent.partition_key_count(),
        ).items
        return await partition(
            self._catalog,
            catalog_id,
            normalized_database,
            normalized_table,
            normalized_values,
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
        page_request = self._paginator.prepare(next_token, max_results)
        selected_segment = PartitionSegment.from_request(segment)
        parsed_expression = self._expression_compiler.parse(expression)
        parent = await table(self._catalog, catalog_id, normalized_database, normalized_table)
        partition_keys = tuple(
            PartitionKey(
                name=str(value.get("Name", "")),
                type_name=str(value.get("Type", "string")),
            )
            for value in parent.definition.get("PartitionKeys", ())
        )
        predicate = self._expression_compiler.bind(parsed_expression, partition_keys)
        values = list(
            await self._catalog.list_partitions(
                catalog_id,
                normalized_database,
                normalized_table,
            )
        )
        candidate_count = len(values)
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_expression.evaluate.before",
            expression_fingerprint=predicate.fingerprint,
            candidate_count=candidate_count,
            segment_number=selected_segment.number if selected_segment is not None else None,
            total_segments=selected_segment.total if selected_segment is not None else None,
            fix_hint=(
                "If a client upgrade changes matched_count, inspect the parse event and update "
                "the isolated grammar, parser, evaluator, or configured type policy."
            ),
        )
        try:
            values = [value for value in values if predicate.matches(value.values)]
        except Exception:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.partition_expression.evaluate.failed",
                expression_fingerprint=predicate.fingerprint,
                candidate_count=candidate_count,
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_expression.evaluate.after",
            expression_fingerprint=predicate.fingerprint,
            candidate_count=candidate_count,
            matched_count=len(values),
        )
        if selected_segment is not None:
            values = [value for value in values if selected_segment.includes(value.values)]
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.partition_expression.segment.after",
                expression_fingerprint=predicate.fingerprint,
                matched_count=len(values),
                segment_number=selected_segment.number,
                total_segments=selected_segment.total,
            )
        return page_request.apply(values)


def _stable_segment(values: tuple[str, ...], total_segments: int) -> int:
    digest = hashlib.sha256("\0".join(values).encode()).digest()
    return int.from_bytes(digest[:8], "big") % total_segments
