"""Compile Glue partition expressions once and evaluate immutable rows.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.partition_expression.evaluator import (
    PartitionExpressionEvaluator,
    PartitionRow,
)
from mystack.glue.application.partition_expression.model import (
    Comparison,
    Expression,
    Logical,
    Membership,
    Negation,
    NullCheck,
    PartitionExpressionPolicy,
    PartitionKey,
    Pattern,
    Range,
)
from mystack.glue.application.partition_expression.parser import PartitionExpressionParser

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CompiledPartitionExpression:
    expression: Expression | None
    keys: tuple[PartitionKey, ...]
    evaluator: PartitionExpressionEvaluator
    fingerprint: str | None

    def matches(self, values: tuple[str | None, ...]) -> bool:
        if self.expression is None:
            return True
        return self.evaluator.matches(self.expression, PartitionRow.create(self.keys, values))


class PartitionExpressionCompiler:
    """Own bounded parsing and schema validation, with no storage dependency."""

    def __init__(self, policy: PartitionExpressionPolicy) -> None:
        self._parser = PartitionExpressionParser(policy)
        self._evaluator = PartitionExpressionEvaluator(policy)

    def compile(
        self,
        source: str | None,
        keys: tuple[PartitionKey, ...],
    ) -> CompiledPartitionExpression:
        if source is None or not source.strip():
            return CompiledPartitionExpression(None, keys, self._evaluator, None)
        fingerprint = hashlib.sha256(source.encode()).hexdigest()[:16]
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_expression.parse.before",
            expression_length=len(source),
            expression_fingerprint=fingerprint,
            partition_key_count=len(keys),
            partition_key_types=[key.type_name for key in keys],
            fix_hint=(
                "Compare the caller dialect with GluePartitionExpression.g4, parser.py, "
                "and evaluator.py; do not add repository parsing."
            ),
        )
        try:
            expression = self._parser.parse(source)
            self._evaluator.validate(expression, keys)
        except Exception:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.partition_expression.parse.failed",
                expression_length=len(source),
                expression_fingerprint=fingerprint,
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.partition_expression.parse.after",
            expression_fingerprint=fingerprint,
            ast_type=type(expression).__name__,
            ast_shape=_expression_shape(expression),
        )
        return CompiledPartitionExpression(expression, keys, self._evaluator, fingerprint)


def _expression_shape(expression: Expression) -> str:
    """Return an operator-only diagnostic tree without fields or literal values."""

    if isinstance(expression, Logical):
        return (
            f"{expression.operator.name}("
            f"{_expression_shape(expression.left)},{_expression_shape(expression.right)})"
        )
    if isinstance(expression, Negation):
        return f"NOT({_expression_shape(expression.operand)})"
    if isinstance(expression, Comparison):
        return f"COMPARISON:{expression.operator.name}"
    if isinstance(expression, Membership):
        return "NOT_IN" if expression.negated else "IN"
    if isinstance(expression, Range):
        return "NOT_BETWEEN" if expression.negated else "BETWEEN"
    if isinstance(expression, Pattern):
        return "NOT_LIKE" if expression.negated else "LIKE"
    if isinstance(expression, NullCheck):
        return "IS_NOT_NULL" if expression.negated else "IS_NULL"
    raise TypeError(f"Unhandled partition expression node: {type(expression).__name__}")
