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
    Expression,
    PartitionExpressionPolicy,
    PartitionKey,
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
            logging.DEBUG,
            "glue.partition_expression.parse.before",
            expression_length=len(source),
            expression_fingerprint=fingerprint,
            partition_key_count=len(keys),
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
            logging.DEBUG,
            "glue.partition_expression.parse.after",
            expression_fingerprint=fingerprint,
            ast_type=type(expression).__name__,
        )
        return CompiledPartitionExpression(expression, keys, self._evaluator, fingerprint)
