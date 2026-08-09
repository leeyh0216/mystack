"""Composable SQLite statement plan for one Glue partition keyset page.

This adapter-local component owns the SQL shape shared by exact predicate pushdown and the
bounded evaluator fallback.  It deliberately accepts only adapter-neutral page facts and bound
parameters; expression compilation and Glue error decisions remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mystack.glue.application.catalog_query_models import PartitionPageQuery

_PARTITION_ROWS = (
    "SELECT p.partition_id, d.catalog_id, d.name, t.name, p.values_json, "
    "p.definition_json, p.creation_time, p.update_time "
    "FROM catalog_partitions AS p "
    "JOIN catalog_tables AS t ON t.table_id = p.table_id "
    "JOIN catalog_databases AS d ON d.database_id = t.database_id "
)


@dataclass(frozen=True, slots=True)
class PartitionSeek:
    order_key: bytes | None
    identifier: int | None

    @property
    def clause(self) -> str:
        if self.order_key is None or self.identifier is None:
            return ""
        return " AND (p.order_key > ? OR (p.order_key = ? AND p.partition_id > ?))"

    def parameters(self) -> tuple[object, ...]:
        if self.order_key is None or self.identifier is None:
            return ()
        return (self.order_key, self.order_key, self.identifier)


@dataclass(frozen=True, slots=True)
class PartitionPagePlan:
    """Build the shared, seek-ordered partition row statement exactly once."""

    table_id: int
    query: PartitionPageQuery
    seek: PartitionSeek

    def statement(
        self,
        *,
        predicate_sql: str | None,
        predicate_parameters: tuple[object, ...] = (),
        joins: tuple[str, ...] = (),
        limit: int | None,
    ) -> tuple[str, tuple[Any, ...]]:
        segment_join, segment_parameters = self._segment_join()
        where = " WHERE p.table_id = ?"
        if predicate_sql is not None:
            where += f" AND ({predicate_sql})"
        sql = (
            _PARTITION_ROWS
            + " ".join((*joins, *segment_join))
            + where
            + self.seek.clause
            + " ORDER BY p.order_key, p.partition_id"
        )
        parameters: tuple[Any, ...] = (
            *segment_parameters,
            self.table_id,
            *predicate_parameters,
            *self.seek.parameters(),
        )
        if limit is not None:
            sql += " LIMIT ?"
            parameters += (limit,)
        return sql, parameters

    def _segment_join(self) -> tuple[tuple[str, ...], tuple[object, ...]]:
        if self.query.total_segments is None:
            return (), ()
        return (
            (
                "JOIN catalog_partition_segments AS ps "
                "ON ps.partition_id = p.partition_id AND ps.total_segments = ? "
                "AND ps.segment_number = ?",
            ),
            (self.query.total_segments, self.query.segment_number),
        )
