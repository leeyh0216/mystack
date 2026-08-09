"""Typed SQLite projection facts for Glue partition values.

Projection conversion is deliberately neutral: invalid data is stored as an invalid projection
fact rather than raising a Glue-domain exception while a write is in progress. The application
preserves its established error precedence when a later expression references that key.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://www.sqlite.org/datatype3.html
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from mystack.glue.application.partition_expression.value_codec import (
    PartitionValueCodec,
    PartitionValueError,
    supported_type_families,
)


@dataclass(frozen=True, slots=True)
class PartitionValueProjection:
    ordinal: int
    type_family: str
    conversion_valid: bool
    string_value: str | None
    date_value: str | None
    timestamp_value: str | None
    numeric_value: str | None


class PartitionValueProjector:
    """Create query-safe typed values without leaking domain errors from the adapter."""

    def __init__(self) -> None:
        self._codec = PartitionValueCodec(supported_type_families())

    def project(
        self,
        ordinal: int,
        raw_value: str | None,
        type_name: str,
    ) -> PartitionValueProjection:
        try:
            family = self._codec.normalized_type(type_name)
        except PartitionValueError:
            return PartitionValueProjection(
                ordinal=ordinal,
                type_family=type_name.strip().casefold() or "unsupported",
                conversion_valid=False,
                string_value=None,
                date_value=None,
                timestamp_value=None,
                numeric_value=None,
            )
        try:
            decoded = self._codec.decode(raw_value, type_name)
        except PartitionValueError:
            return PartitionValueProjection(
                ordinal=ordinal,
                type_family=family,
                conversion_valid=False,
                string_value=None,
                date_value=None,
                timestamp_value=None,
                numeric_value=None,
            )
        if decoded is None:
            return PartitionValueProjection(
                ordinal=ordinal,
                type_family=family,
                conversion_valid=True,
                string_value=None,
                date_value=None,
                timestamp_value=None,
                numeric_value=None,
            )
        if family == "string":
            return PartitionValueProjection(ordinal, family, True, str(decoded), None, None, None)
        if family == "date":
            assert isinstance(decoded, date)
            return PartitionValueProjection(
                ordinal, family, True, None, decoded.isoformat(), None, None
            )
        if family == "timestamp":
            assert isinstance(decoded, datetime)
            return PartitionValueProjection(
                ordinal,
                family,
                True,
                None,
                None,
                decoded.isoformat(timespec="microseconds"),
                None,
            )
        if isinstance(decoded, int | Decimal):
            return PartitionValueProjection(ordinal, family, True, None, None, None, str(decoded))
        raise AssertionError(f"Unhandled normalized Glue partition type {family!r}")

    def type_family(self, type_name: str) -> str:
        """Resolve one already-bound partition key type without exposing a domain failure."""

        return self._codec.normalized_type(type_name)

    def literal(self, value: str | None, type_name: str) -> str | None:
        """Return the same normalized value that a valid stored projection uses."""

        if value is None:
            return None
        projection = self.project(0, value, type_name)
        if not projection.conversion_valid:
            raise PartitionValueError(f"Partition value is not valid for key type {type_name!r}")
        for candidate in (
            projection.string_value,
            projection.date_value,
            projection.timestamp_value,
            projection.numeric_value,
        ):
            if candidate is not None:
                return candidate
        raise AssertionError("A non-null valid partition literal did not produce a projection")
