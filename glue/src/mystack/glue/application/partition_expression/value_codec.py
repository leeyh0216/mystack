"""Pure partition value conversion shared by the evaluator and storage projections.

This module intentionally has no Glue-domain dependency. The application maps its neutral
``PartitionValueError`` to the modeled wire error, while the SQLite adapter records conversion
state without choosing a domain failure.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://docs.python.org/3/library/datetime.html#datetime.date.fromisoformat
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_INTEGER_TYPES = {"int", "bigint", "long", "tinyint", "smallint"}
_DECIMAL_TYPE = re.compile(r"^decimal(?:\(\d+\s*,\s*\d+\))?$")


class PartitionValueError(ValueError):
    """Neutral conversion failure; application policy selects the public Glue error."""


class LikePatternCompiler:
    """Compile Glue SQL and Spark Hive metastore ``LIKE`` pattern dialects.

    Spark 3.5 converts StartsWith/EndsWith/Contains partition predicates to ``.*`` patterns before
    it submits them through the Glue Hive client:
    https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala
    """

    def compile(self, value: str) -> str:
        import re as regular_expression

        parts: list[str] = []
        position = 0
        escaped = False
        while position < len(value):
            character = value[position]
            if escaped:
                parts.append(regular_expression.escape(character))
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "%":
                parts.append(".*")
            elif character == "_":
                parts.append(".")
            elif character == "." and position + 1 < len(value) and value[position + 1] == "*":
                parts.append(".*")
                position += 1
            else:
                parts.append(regular_expression.escape(character))
            position += 1
        if escaped:
            parts.append(regular_expression.escape("\\"))
        return "".join(parts)


class PartitionValueCodec:
    """Convert catalog strings and expression literals through one configured type policy."""

    def __init__(self, supported_key_types: Iterable[str]) -> None:
        self._supported = {value.casefold() for value in supported_key_types}

    def normalized_type(self, type_name: str) -> str:
        normalized = type_name.strip().casefold()
        family = "decimal" if _DECIMAL_TYPE.fullmatch(normalized) else normalized
        if family not in self._supported:
            raise PartitionValueError(
                f"Partition key type {type_name!r} is not supported in expressions"
            )
        return family

    def decode(self, value: str | None, type_name: str) -> Any | None:
        if value is None:
            return None
        family = self.normalized_type(type_name)
        try:
            if family == "string":
                return value
            if family in _INTEGER_TYPES:
                return int(value)
            if family == "decimal":
                parsed = Decimal(value)
                if not parsed.is_finite():
                    raise InvalidOperation
                return parsed
            if family == "date":
                return date.fromisoformat(value)
            if family == "timestamp":
                return self.timestamp(value)
        except (InvalidOperation, TypeError, ValueError) as error:
            raise PartitionValueError(
                f"Partition value is not valid for key type {type_name!r}"
            ) from error
        raise PartitionValueError(f"Partition key type {type_name!r} is not supported")

    @staticmethod
    def timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed


def supported_type_families() -> tuple[str, ...]:
    """Return all type families known to the current Glue expression protocol implementation."""

    return ("string", "date", "timestamp", *_INTEGER_TYPES, "decimal")
