"""Extract code-owned inbound operation inventories without importing emulator packages.

This parser is intentionally literal-only. It lets the botocore-only upstream-drift workflow use
the same reviewed operation registrations as the full workspace while failing closed if the source
inventory shape changes.

References:
- https://docs.python.org/3/library/ast.html
- https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OperationInventoryError(ValueError):
    """A source-owned inventory is absent, dynamic, ambiguous, or otherwise unsafe to extract."""


@dataclass(frozen=True, slots=True)
class InventorySource:
    """One literal `frozenset` declaration owned by an inbound adapter module."""

    relative_path: str
    symbol: str


SOURCES: Mapping[str, InventorySource] = {
    "emr": InventorySource(
        "emr/src/mystack/emr/adapters/inbound/aws_operations.py",
        "IMPLEMENTED_EMR_OPERATIONS",
    ),
    "glue": InventorySource(
        "glue/src/mystack/glue/adapters/inbound/aws_operations.py",
        "IMPLEMENTED_GLUE_OPERATIONS",
    ),
}


def extract_implemented_operation_inventory(
    root: Path = ROOT,
    *,
    sources: Mapping[str, InventorySource] = SOURCES,
) -> dict[str, frozenset[str]]:
    """Return source-owned operation sets via strict AST parsing, never a default fallback."""

    expected_services = {"emr", "glue"}
    if set(sources) != expected_services:
        raise OperationInventoryError(
            f"inventory sources must define exactly emr and glue actual={sorted(sources)}"
        )
    return {
        service: _extract_frozenset_literal(root / source.relative_path, source.symbol)
        for service, source in sorted(sources.items())
    }


def _extract_frozenset_literal(path: Path, symbol: str) -> frozenset[str]:
    try:
        document = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as error:
        raise OperationInventoryError(
            f"cannot parse inventory source path={path}: {error}"
        ) from error
    assignments = [
        node
        for node in document.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == symbol
    ]
    if len(assignments) != 1:
        raise OperationInventoryError(
            "inventory must have exactly one top-level assignment "
            f"path={path} symbol={symbol!r} count={len(assignments)}"
        )
    value = assignments[0].value
    if (
        not isinstance(value, ast.Call)
        or not isinstance(value.func, ast.Name)
        or value.func.id != "frozenset"
        or value.keywords
        or len(value.args) != 1
        or not isinstance(value.args[0], ast.Set)
    ):
        raise OperationInventoryError(
            'inventory must be a literal frozenset({"Operation", ...}) '
            f"path={path} symbol={symbol!r}"
        )
    values = value.args[0].elts
    if not values or any(
        not isinstance(item, ast.Constant) or not isinstance(item.value, str) for item in values
    ):
        raise OperationInventoryError(
            f"inventory values must be non-empty string literals path={path} symbol={symbol!r}"
        )
    operations = [item.value for item in values]
    if any(not operation for operation in operations) or len(operations) != len(set(operations)):
        raise OperationInventoryError(
            "inventory values must be unique non-empty operation names "
            f"path={path} symbol={symbol!r}"
        )
    return frozenset(operations)
