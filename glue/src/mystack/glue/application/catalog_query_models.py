"""Application-owned bounded Catalog query models.

The models deliberately describe a page in terms of immutable domain values and an opaque seek
position. They contain no SQL strings, DB-API values, or transport request objects. Outbound
adapters may turn them into indexed queries; inbound handlers retain Glue validation and error
precedence.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://www.sqlite.org/queryplanner.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from mystack.glue.application.partition_expression.service import CompiledPartitionExpression

_Item = TypeVar("_Item")


@dataclass(frozen=True, slots=True)
class SeekCursor:
    """One adapter-neutral lexicographic seek position.

    The token carries only a surrogate identifier, never a raw partition value or a database/table
    name. The adapter resolves its private sort key under the query's already-validated scope.
    """

    identifier: int

    def __post_init__(self) -> None:
        if self.identifier <= 0:
            raise ValueError("Seek cursor identifier must be positive")


@dataclass(frozen=True, slots=True)
class CatalogPage(Generic[_Item]):
    """A bounded result page; ordinary AWS responses never imply a total count."""

    values: tuple[_Item, ...]
    next_cursor: SeekCursor | None
    fetched_count: int
    query_strategy: str
    invalid_cursor: bool = False


@dataclass(frozen=True, slots=True)
class PartitionCatalogPage(CatalogPage[_Item]):
    """A page plus a value-safe stored-value validation outcome.

    The adapter reports only the partition key type. The application turns it into the modeled
    Glue ``InvalidInputException`` without exposing a partition value in logs or an error body.
    """

    invalid_partition_key_type: str | None = None
    invalid_partition_value_count: bool = False


@dataclass(frozen=True, slots=True)
class DatabasePageQuery:
    catalog_id: str
    page_size: int
    after: SeekCursor | None


@dataclass(frozen=True, slots=True)
class TablePageQuery:
    catalog_id: str
    database_name: str
    page_size: int
    after: SeekCursor | None
    name_pattern: str | None


@dataclass(frozen=True, slots=True)
class PartitionPageQuery:
    catalog_id: str
    database_name: str
    table_name: str
    page_size: int
    after: SeekCursor | None
    predicate: CompiledPartitionExpression
    segment_number: int | None
    total_segments: int | None
