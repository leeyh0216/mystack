"""Operation-family registration invariants.

Official operation inventory:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from mystack.aws_protocol import OperationFamily, OperationFamilyRegistry


async def _handler(payload, context) -> Mapping[str, Any]:
    del payload, context
    return {}


def test_registry_merges_complete_families() -> None:
    dispatcher = OperationFamilyRegistry("test", {"One", "Two"}).dispatcher(
        (
            OperationFamily("first", {"One": _handler}),
            OperationFamily("second", {"Two": _handler}),
        )
    )

    assert dispatcher.operations == {"One", "Two"}


def test_registry_rejects_duplicate_ownership() -> None:
    with pytest.raises(ValueError, match="owned by both"):
        OperationFamilyRegistry("test", {"One"}).dispatcher(
            (
                OperationFamily("first", {"One": _handler}),
                OperationFamily("second", {"One": _handler}),
            )
        )


@pytest.mark.parametrize(
    ("expected", "family", "message"),
    [
        ({"One", "Two"}, OperationFamily("only", {"One": _handler}), "missing=\\['Two'\\]"),
        ({"One"}, OperationFamily("extra", {"One": _handler, "Two": _handler}), "unexpected"),
    ],
)
def test_registry_rejects_missing_or_unclassified_handlers(expected, family, message) -> None:
    with pytest.raises(ValueError, match=message):
        OperationFamilyRegistry("test", expected).dispatcher((family,))
