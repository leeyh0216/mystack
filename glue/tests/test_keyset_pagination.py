"""Contracts for opaque, request-bound SQLite keyset pagination."""

from __future__ import annotations

import pytest
from mystack.glue.application.catalog_query_models import SeekCursor
from mystack.glue.application.pagination import Paginator
from mystack.glue.domain import InvalidInputError


def test_keyset_token_round_trip_is_bound_to_the_same_query_context() -> None:
    paginator = Paginator(100)
    context = paginator.context("123", "analytics", "events", "predicate", None)
    request = paginator.prepare_keyset(None, 10).bind(context)

    token = paginator.complete_keyset(request, SeekCursor(42))

    resumed = paginator.prepare_keyset(token, 10).bind(context)
    assert resumed.cursor == SeekCursor(42)


def test_keyset_token_is_rejected_for_a_different_catalog_query() -> None:
    paginator = Paginator(100)
    original = paginator.context("123", "analytics", "events", "predicate", None)
    request = paginator.prepare_keyset(None, 10).bind(original)
    token = paginator.complete_keyset(request, SeekCursor(42))

    with pytest.raises(InvalidInputError, match="does not match"):
        paginator.prepare_keyset(token, 10).bind(
            paginator.context("123", "analytics", "other-events", "predicate", None)
        )


@pytest.mark.parametrize("token", ("not-a-token", "e30=", "eyJ2IjoxfQ=="))
def test_malformed_keyset_tokens_are_rejected_deterministically(token: str) -> None:
    with pytest.raises(InvalidInputError, match="Invalid pagination token"):
        Paginator(100).prepare_keyset(token, 10)
