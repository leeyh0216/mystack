"""SQLite UDFs and collations for protocol-compatible bounded Catalog queries.

The functions return SQL three-valued values (``1``, ``0``, or ``NULL``) and never include raw
catalog values in logging. SQL construction remains in ``query_compiler.py``.

References:
- https://www.sqlite.org/appfunc.html
- https://www.sqlite.org/datatype3.html#collation
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from mystack.glue.application.partition_expression.value_codec import LikePatternCompiler


def register_query_functions(connection: Any) -> None:
    """Register deterministic functions/collations before a schema creates dependent indexes."""

    connection.create_collation("MYSTACK_NUMERIC", _numeric_collation)
    connection.create_function("mystack_glue_like", 2, _glue_like, deterministic=True)
    connection.create_function("mystack_glue_regex", 2, _glue_regex, deterministic=True)


def _numeric_collation(left: str, right: str) -> int:
    """Compare finite Decimal text exactly; invalid rows are excluded before this runs."""

    try:
        left_value = Decimal(left)
        right_value = Decimal(right)
        if not left_value.is_finite() or not right_value.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return (left > right) - (left < right)
    return (left_value > right_value) - (left_value < right_value)


def _glue_like(value: str | None, pattern: str | None) -> int | None:
    if value is None or pattern is None:
        return None
    return int(bool(_like_pattern(pattern).fullmatch(value)))


def _glue_regex(pattern: str | None, value: str | None) -> int | None:
    if value is None or pattern is None:
        return None
    return int(bool(_regex_pattern(pattern).search(value)))


@lru_cache(maxsize=128)
def _like_pattern(value: str) -> re.Pattern[str]:
    return re.compile(LikePatternCompiler().compile(value), re.DOTALL)


@lru_cache(maxsize=128)
def _regex_pattern(value: str) -> re.Pattern[str]:
    return re.compile(value)
