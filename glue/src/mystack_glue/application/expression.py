"""Small, explicit Glue partition-expression evaluator.

The supported predicate subset covers equality/inequality comparisons joined by AND,
which is the common shape emitted by Hive/Spark partition pruning. Unsupported grammar
fails with InvalidInputException rather than silently returning incorrect partitions.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from mystack_glue.domain import InvalidInputError

_TERM = re.compile(
    r"^\s*\(?\s*`?(?P<name>[A-Za-z_][\w]*)`?\s*"
    r"(?P<operator>=|==|!=|<>)\s*"
    r"(?P<quote>['\"])(?P<value>(?:\\.|(?!\3).)*)\3\s*\)?\s*$"
)


def matches_partition(expression: str | None, values: Mapping[str, str]) -> bool:
    if not expression:
        return True
    terms = re.split(r"\s+(?i:AND)\s+", expression.strip())
    for term in terms:
        match = _TERM.match(term)
        if match is None:
            raise InvalidInputError(
                "Unsupported partition expression. Mystack currently supports quoted "
                "equality/inequality predicates joined by AND."
            )
        actual = values.get(match.group("name"))
        expected = bytes(match.group("value"), "utf-8").decode("unicode_escape")
        equal = actual == expected
        if match.group("operator") in {"=", "=="} and not equal:
            return False
        if match.group("operator") in {"!=", "<>"} and equal:
            return False
    return True
