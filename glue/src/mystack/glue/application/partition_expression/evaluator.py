"""Typed, three-valued evaluation of parsed Glue partition expressions.

Glue stores partition values as ordered strings but evaluates the key types listed
by ``GetPartitions``:
https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from mystack.glue.application.partition_expression.model import (
    Comparison,
    Expression,
    Literal,
    Logical,
    Membership,
    Negation,
    NullCheck,
    PartitionExpressionPolicy,
    PartitionKey,
    Pattern,
    Range,
    TokenKind,
)
from mystack.glue.application.partition_expression.value_codec import (
    LikePatternCompiler,
    PartitionValueCodec,
    PartitionValueError,
)
from mystack.glue.domain import InvalidInputError


class TruthValue(Enum):
    FALSE = 0
    TRUE = 1
    UNKNOWN = 2

    def negate(self) -> TruthValue:
        if self is TruthValue.UNKNOWN:
            return self
        return TruthValue.FALSE if self is TruthValue.TRUE else TruthValue.TRUE


@dataclass(frozen=True, slots=True)
class PartitionRow:
    schema: dict[str, PartitionKey]
    values: dict[str, str | None]

    @classmethod
    def create(
        cls,
        keys: tuple[PartitionKey, ...],
        values: tuple[str | None, ...],
    ) -> PartitionRow:
        if len(keys) != len(values):
            raise InvalidInputError("Partition value count does not match partition key count")
        schema: dict[str, PartitionKey] = {}
        mapped_values: dict[str, str | None] = {}
        for key, value in zip(keys, values, strict=True):
            normalized = key.name.casefold()
            if normalized in schema:
                raise InvalidInputError("Partition key names must be unique ignoring case")
            schema[normalized] = key
            mapped_values[normalized] = value
        return cls(schema, mapped_values)


class PartitionExpressionEvaluator:
    """Evaluate an AST without parsing, I/O, pagination, or repository access."""

    def __init__(self, policy: PartitionExpressionPolicy) -> None:
        self._codec = PartitionValueCodec(policy.supported_key_types)
        self._like_patterns = LikePatternCompiler()

    def validate(self, expression: Expression, keys: tuple[PartitionKey, ...]) -> None:
        schema = PartitionRow.create(keys, (None,) * len(keys)).schema
        try:
            for field in self._fields(expression):
                key = schema.get(field.casefold())
                if key is None:
                    raise InvalidInputError(f"Unknown partition key {field!r} in expression")
                self._codec.normalized_type(key.type_name)
        except PartitionValueError as error:
            raise InvalidInputError(str(error)) from error

    def matches(self, expression: Expression, row: PartitionRow) -> bool:
        return self._evaluate(expression, row) is TruthValue.TRUE

    def _evaluate(self, expression: Expression, row: PartitionRow) -> TruthValue:
        if isinstance(expression, Logical):
            left = self._evaluate(expression.left, row)
            right = self._evaluate(expression.right, row)
            if expression.operator is TokenKind.AND:
                if TruthValue.FALSE in {left, right}:
                    return TruthValue.FALSE
                return TruthValue.TRUE if left is right is TruthValue.TRUE else TruthValue.UNKNOWN
            if TruthValue.TRUE in {left, right}:
                return TruthValue.TRUE
            return TruthValue.FALSE if left is right is TruthValue.FALSE else TruthValue.UNKNOWN
        if isinstance(expression, Negation):
            return self._evaluate(expression.operand, row).negate()
        key, actual = self._field(expression.field, row)
        if isinstance(expression, NullCheck):
            result = TruthValue.TRUE if actual is None else TruthValue.FALSE
            return result.negate() if expression.negated else result
        if isinstance(expression, Comparison):
            expected = self._literal(expression.value, key)
            if actual is None or expected is None:
                return TruthValue.UNKNOWN
            comparisons = {
                TokenKind.EQ: actual == expected,
                TokenKind.NE: actual != expected,
                TokenKind.GT: actual > expected,
                TokenKind.GE: actual >= expected,
                TokenKind.LT: actual < expected,
                TokenKind.LE: actual <= expected,
            }
            return self._truth(comparisons[expression.operator])
        if isinstance(expression, Membership):
            if actual is None:
                return TruthValue.UNKNOWN
            candidates = [self._literal(value, key) for value in expression.values]
            if actual in candidates:
                result = TruthValue.TRUE
            elif None in candidates:
                result = TruthValue.UNKNOWN
            else:
                result = TruthValue.FALSE
            return result.negate() if expression.negated else result
        if isinstance(expression, Range):
            lower = self._literal(expression.lower, key)
            upper = self._literal(expression.upper, key)
            if actual is None or lower is None or upper is None:
                return TruthValue.UNKNOWN
            result = self._truth(lower <= actual <= upper)
            return result.negate() if expression.negated else result
        if isinstance(expression, Pattern):
            if self._codec.normalized_type(key.type_name) != "string":
                raise InvalidInputError("LIKE is supported only for string partition keys")
            expected = self._literal(expression.value, key)
            if actual is None or expected is None:
                return TruthValue.UNKNOWN
            result = self._truth(
                bool(re.fullmatch(self._like_patterns.compile(expected), actual, re.DOTALL))
            )
            return result.negate() if expression.negated else result
        raise TypeError(f"Unhandled partition expression node: {type(expression).__name__}")

    def _field(self, field: str, row: PartitionRow) -> tuple[PartitionKey, Any | None]:
        normalized = field.casefold()
        key = row.schema.get(normalized)
        if key is None:
            raise InvalidInputError(f"Unknown partition key {field!r} in expression")
        return key, self._decode(row.values[normalized], key.type_name)

    def _literal(self, literal: Literal, key: PartitionKey) -> Any | None:
        return self._decode(literal.value, key.type_name)

    def _decode(self, value: str | None, type_name: str) -> Any | None:
        try:
            return self._codec.decode(value, type_name)
        except PartitionValueError as error:
            raise InvalidInputError(str(error)) from error

    @staticmethod
    def _truth(value: bool) -> TruthValue:
        return TruthValue.TRUE if value else TruthValue.FALSE

    @classmethod
    def _fields(cls, expression: Expression) -> tuple[str, ...]:
        if isinstance(expression, Logical):
            return cls._fields(expression.left) + cls._fields(expression.right)
        if isinstance(expression, Negation):
            return cls._fields(expression.operand)
        return (expression.field,)
