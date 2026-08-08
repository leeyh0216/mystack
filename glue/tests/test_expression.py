"""Glue GetPartitions SQL expression grammar and typed evaluation contracts.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala
"""

from __future__ import annotations

import logging

import pytest
from mystack.glue.application.partition_expression import (
    PartitionExpressionCompiler,
    PartitionExpressionPolicy,
    PartitionKey,
)
from mystack.glue.domain import InvalidInputError

_SUPPORTED_TYPES = (
    "string",
    "date",
    "timestamp",
    "int",
    "bigint",
    "long",
    "tinyint",
    "smallint",
    "decimal",
)


def _compiler(*, max_length: int = 2048, max_tokens: int = 512):
    return PartitionExpressionCompiler(
        PartitionExpressionPolicy(max_length, max_tokens, _SUPPORTED_TYPES)
    )


def _matches(
    expression: str,
    values: tuple[str | None, ...],
    keys: tuple[PartitionKey, ...] = (
        PartitionKey("day", "date"),
        PartitionKey("region", "string"),
    ),
) -> bool:
    return _compiler().compile(expression, keys).matches(values)


@pytest.mark.parametrize(
    ("expression", "expected"),
    (
        ("day = '2026-08-09'", True),
        ("day <> '2026-08-09'", False),
        ("day != '2026-08-08'", True),
        ("day > '2026-08-08'", True),
        ("day >= '2026-08-09'", True),
        ("day < '2026-08-10'", True),
        ("day <= '2026-08-08'", False),
    ),
)
def test_comparison_operators(expression: str, expected: bool) -> None:
    assert _matches(expression, ("2026-08-09", "ap-northeast-2")) is expected


def test_precedence_parentheses_and_negation() -> None:
    values = ("2026-08-09", "ap-northeast-2")
    assert _matches("day='2026-08-08' OR day='2026-08-09' AND region LIKE 'ap-%'", values)
    assert not _matches(
        "(day='2026-08-08' OR day='2026-08-09') AND NOT region LIKE 'ap-%'",
        values,
    )


@pytest.mark.parametrize(
    "expression",
    (
        "region IN ('us-east-1', 'ap-northeast-2')",
        "region NOT IN ('us-east-1')",
        "day BETWEEN '2026-08-01' AND '2026-08-31'",
        "day NOT BETWEEN '2025-01-01' AND '2025-12-31'",
        "region LIKE 'ap-_ortheast-2'",
        "region NOT LIKE 'us-%'",
        "region IS NOT NULL",
    ),
)
def test_documented_logical_predicates(expression: str) -> None:
    assert _matches(expression, ("2026-08-09", "ap-northeast-2"))


@pytest.mark.parametrize(
    "expression",
    (
        "region LIKE 'ap-.*'",
        "region LIKE '.*northeast-2'",
        "region LIKE '.*northeast.*'",
    ),
)
def test_spark_hive_like_patterns(expression: str) -> None:
    """Spark HiveShim uses ``.*`` for StartsWith, EndsWith, and Contains."""

    assert _matches(expression, ("2026-08-09", "ap-northeast-2"))


def test_spark_3_5_partition_pruning_expression() -> None:
    expression = "event_date >= '2026-08-08' and event_date <= '2026-08-31' and region like 'ap-.*'"
    keys = (
        PartitionKey("event_date", "date"),
        PartitionKey("region", "string"),
    )
    predicate = _compiler().compile(expression, keys)

    assert predicate.matches(("2026-08-08", "ap-northeast-2"))
    assert predicate.matches(("2026-08-09", "ap-southeast-1"))
    assert not predicate.matches(("2025-01-01", "us-east-1"))


def test_expression_logs_are_value_safe_and_actionable(caplog) -> None:
    expression = "region LIKE 'private-partition-.*'"
    with caplog.at_level(logging.INFO):
        _compiler().compile(expression, (PartitionKey("region", "string"),))

    fields = [
        getattr(record, "mystack_fields", {})
        for record in caplog.records
        if str(record.msg).startswith("glue.partition_expression.parse.")
    ]
    assert fields
    assert any(value.get("ast_shape") == "LIKE" for value in fields)
    assert any("fix_hint" in value for value in fields)
    assert all("private-partition" not in repr(value) for value in fields)


def test_is_null_and_sql_unknown_semantics() -> None:
    keys = (PartitionKey("optional", "string"),)
    assert _matches("optional IS NULL", (None,), keys)
    assert not _matches("optional = NULL", (None,), keys)
    assert not _matches("NOT optional = NULL", (None,), keys)


@pytest.mark.parametrize(
    ("type_name", "actual", "expression"),
    (
        ("string", "west", "value > 'east'"),
        ("date", "2026-08-09", "value < '2026-08-10'"),
        ("timestamp", "2026-08-09T01:02:03Z", "value >= '2026-08-09 01:02:03'"),
        ("int", "10", "value > 2"),
        ("bigint", "10", "value = 10"),
        ("long", "10", "value = 10"),
        ("tinyint", "10", "value = 10"),
        ("smallint", "10", "value = 10"),
        ("decimal(18, 4)", "10.2500", "value BETWEEN 10.2 AND 10.3"),
    ),
)
def test_supported_partition_key_types(
    type_name: str,
    actual: str,
    expression: str,
) -> None:
    assert _matches(expression, (actual,), (PartitionKey("value", type_name),))


def test_quoted_identifiers_and_sql_quote_escaping() -> None:
    assert _matches(
        "`release day` = 'it''s-ready'",
        ("it's-ready",),
        (PartitionKey("release day", "string"),),
    )


@pytest.mark.parametrize(
    ("expression", "keys", "values"),
    (
        ("day >", (PartitionKey("day", "date"),), ("2026-08-09",)),
        ("missing = 'x'", (PartitionKey("day", "date"),), ("2026-08-09",)),
        ("flag = 'true'", (PartitionKey("flag", "boolean"),), ("true",)),
        ("day > 'not-a-date'", (PartitionKey("day", "date"),), ("2026-08-09",)),
        ("amount LIKE '1%'", (PartitionKey("amount", "int"),), ("10",)),
    ),
)
def test_invalid_syntax_key_type_and_value_are_explicit(
    expression: str,
    keys: tuple[PartitionKey, ...],
    values: tuple[str, ...],
) -> None:
    with pytest.raises(InvalidInputError):
        _compiler().compile(expression, keys).matches(values)


def test_expression_limits_are_policy_driven() -> None:
    key = (PartitionKey("day", "string"),)
    with pytest.raises(InvalidInputError, match="characters"):
        _compiler(max_length=5).compile("day='x'", key)
    with pytest.raises(InvalidInputError, match="tokens"):
        _compiler(max_tokens=2).compile("day='x'", key)


def test_integer_range_property_is_ordered_numerically() -> None:
    for value in range(-25, 26):
        assert _matches(
            "value BETWEEN 2 AND 11",
            (str(value),),
            (PartitionKey("value", "int"),),
        ) is (2 <= value <= 11)
