"""Partition pruning expression subset tests.

Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
"""

import pytest
from mystack.glue.application.expression import matches_partition
from mystack.glue.domain import InvalidInputError


def test_and_equality_expression() -> None:
    assert matches_partition(
        "day='2026-08-08' AND region != 'us-east-1'",
        {
            "day": "2026-08-08",
            "region": "ap-northeast-2",
        },
    )


def test_unsupported_expression_fails_explicitly() -> None:
    with pytest.raises(InvalidInputError):
        matches_partition("day > '2026-08-08'", {"day": "2026-08-09"})
