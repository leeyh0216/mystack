"""Strict source-level operation inventory extraction contracts.

Reference: https://docs.python.org/3/library/ast.html
"""

from __future__ import annotations

import pytest

from scripts.operation_inventory import (
    OperationInventoryError,
    _extract_frozenset_literal,
    extract_implemented_operation_inventory,
)


def test_extractor_reads_each_code_owned_service_inventory() -> None:
    inventory = extract_implemented_operation_inventory()

    assert set(inventory) == {"emr", "glue"}
    assert "RunJobFlow" in inventory["emr"]
    assert "GetTable" in inventory["glue"]


def test_extractor_rejects_dynamic_operation_inventory_shape(tmp_path) -> None:
    source = tmp_path / "aws_operations.py"
    source.write_text(
        "IMPLEMENTED_EMR_OPERATIONS = frozenset(load_operations())\n", encoding="utf-8"
    )

    with pytest.raises(OperationInventoryError, match="literal frozenset"):
        _extract_frozenset_literal(source, "IMPLEMENTED_EMR_OPERATIONS")
