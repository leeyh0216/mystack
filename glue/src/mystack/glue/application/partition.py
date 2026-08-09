"""Focused Glue partition command and query handlers.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.catalog_identity import name, partition, table
from mystack.glue.application.catalog_ports import (
    CatalogQueryPort,
    CatalogReadPort,
    CatalogWritePort,
)
from mystack.glue.application.catalog_query_models import PartitionPageQuery
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.partition_expression import (
    PartitionExpressionCompiler,
    PartitionKey,
)
from mystack.glue.application.partition_segments import stable_partition_segment
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
        return stable_partition_segment(values, self.total) == self.number


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
        read_catalog: CatalogReadPort,
        query_catalog: CatalogQueryPort,
        paginator: Paginator,
        expression_compiler: PartitionExpressionCompiler,
    ) -> None:
        self._read_catalog = read_catalog
        self._query_catalog = query_catalog
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
        parent = await table(self._read_catalog, catalog_id, normalized_database, normalized_table)
        normalized_values = PartitionValues.from_items(
            values,
            expected_count=parent.partition_key_count(),
        ).items
        return await partition(
            self._read_catalog,
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
        page_request = self._paginator.prepare_keyset(next_token, max_results)
        selected_segment = PartitionSegment.from_request(segment)
        parsed_expression = self._expression_compiler.parse(expression)
        parent = await table(self._read_catalog, catalog_id, normalized_database, normalized_table)
        partition_keys = tuple(
            PartitionKey(
                name=str(value.get("Name", "")),
                type_name=str(value.get("Type", "string")),
            )
            for value in parent.definition.get("PartitionKeys", ())
        )
        predicate = self._expression_compiler.bind(parsed_expression, partition_keys)
        page_request = page_request.bind(
            self._paginator.context(
                "partitions",
                catalog_id,
                normalized_database,
                normalized_table,
                predicate.fingerprint,
                segment,
            )
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_query.plan.before",
            expression_fingerprint=predicate.fingerprint,
            ast_type=(
                None if predicate.expression is None else type(predicate.expression).__name__
            ),
            query_strategy="sqlite-keyset-pushdown",
            cursor_present=page_request.cursor is not None,
            page_size=page_request.size,
            segment_number=None if selected_segment is None else selected_segment.number,
            total_segments=None if selected_segment is None else selected_segment.total,
            fix_hint=(
                "Inspect application/partition_expression for grammar or type semantics, then "
                "sqlite_catalog/query_compiler.py and schema.py for SQLite pushdown behavior."
            ),
        )
        first = await self._query_catalog.first_partition(
            catalog_id,
            normalized_database,
            normalized_table,
        )
        if first is None and page_request.cursor is None:
            return [], None
        if first is not None:
            # Preserve the historical row-by-row evaluator precedence before SQLite compiles
            # typed literals. In particular, an empty table never forces literal conversion.
            predicate.matches(first.values)
        page = await self._query_catalog.page_partitions(
            PartitionPageQuery(
                catalog_id,
                normalized_database,
                normalized_table,
                page_request.size,
                page_request.cursor,
                predicate,
                None if selected_segment is None else selected_segment.number,
                None if selected_segment is None else selected_segment.total,
                self._expression_compiler.fallback_max_candidates,
            )
        )
        if page.invalid_cursor:
            raise InvalidInputError("Pagination token does not match this request")
        if page.invalid_partition_key_type is not None:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.partition_query.preflight.failed",
                expression_fingerprint=predicate.fingerprint,
                issue_kind="invalid_typed_partition_value",
                partition_key_type=page.invalid_partition_key_type,
                fix_hint=(
                    "Inspect the table partition-key type and the persisted value; the SQLite "
                    "projection intentionally preserves Glue evaluator error behavior."
                ),
            )
            raise InvalidInputError(
                f"Partition value is not valid for key type {page.invalid_partition_key_type!r}"
            )
        if page.invalid_partition_value_count:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.partition_query.preflight.failed",
                expression_fingerprint=predicate.fingerprint,
                issue_kind="partition_value_count_mismatch",
                fix_hint=(
                    "Inspect UpdateTable partition-key changes and partition value cardinality; "
                    "the query adapter does not infer or pad values."
                ),
            )
            raise InvalidInputError("Partition value count does not match partition key count")
        if page.fallback_candidate_limit_exceeded:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.partition_query.fallback.limit_exceeded",
                expression_fingerprint=predicate.fingerprint,
                candidate_limit=self._expression_compiler.fallback_max_candidates,
                fix_hint="Narrow the partition expression and retry within the configured bound.",
            )
            raise InvalidInputError(
                "Partition expression fallback exceeded the configured candidate limit; "
                "narrow the request and retry"
            )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_query.after",
            expression_fingerprint=predicate.fingerprint,
            query_strategy=page.query_strategy,
            returned_count=page.fetched_count,
            has_next=page.next_cursor is not None,
            segment_number=None if selected_segment is None else selected_segment.number,
            total_segments=None if selected_segment is None else selected_segment.total,
        )
        return list(page.values), self._paginator.complete_keyset(page_request, page.next_cursor)
