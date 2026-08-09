"""Pytest collection adapter for typed Mystack compatibility evidence.

The adapter writes only when ``--mystack-compatibility-output`` is supplied.  It is deliberately
collection-only: tests, fixtures, Docker Compose, and network clients are never invoked by this
module.

References:
- https://docs.pytest.org/en/stable/how-to/usage.html
- https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from test_support.compatibility import EvidenceValidationError, ExecutionKind, marker_payload


class CompatibilityCollectionError(ValueError):
    """Collected pytest evidence cannot become a deterministic CI case."""


def collect_compatibility_items(items: Iterable[pytest.Item]) -> dict[str, Any]:
    """Collect registered markers into deterministic primitive data without running tests."""

    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        markers = tuple(item.iter_markers("mystack_compatibility"))
        if not markers:
            continue
        if len(markers) != 1:
            raise CompatibilityCollectionError(
                f"test must declare exactly one mystack_compatibility marker nodeid={item.nodeid}"
            )
        marker = markers[0]
        if marker.args:
            raise CompatibilityCollectionError(
                f"mystack_compatibility accepts keyword-only metadata nodeid={item.nodeid}"
            )
        try:
            payload = marker_payload(marker.kwargs)
        except EvidenceValidationError as error:
            raise CompatibilityCollectionError(
                f"invalid evidence nodeid={item.nodeid}: {error}"
            ) from error
        _validate_execution_marker(item, payload)
        _merge(grouped, item.nodeid, payload)

    if not grouped:
        raise CompatibilityCollectionError("no mystack_compatibility markers were collected")
    return {
        "schema_version": 1,
        "generated_from": "pytest mystack_compatibility markers",
        "cases": [grouped[case_id] for case_id in sorted(grouped)],
    }


def write_collection(path: Path, document: dict[str, Any]) -> None:
    """Atomically persist a canonical collection result for a later pure compiler."""

    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register an opt-in output path without changing normal pytest execution."""

    group = parser.getgroup("mystack compatibility evidence")
    group.addoption(
        "--mystack-compatibility-output",
        action="store",
        default=None,
        metavar="PATH",
        help="write collected mystack_compatibility markers as deterministic JSON",
    )
    group.addoption(
        "--mystack-compatibility-forbidden-import",
        action="append",
        default=[],
        metavar="PACKAGE",
        help="fail collection when PACKAGE is imported by annotated test modules",
    )


def pytest_collection_finish(session: pytest.Session) -> None:
    """Write evidence after pytest has resolved parameterized node IDs and markers."""

    configured = session.config.getoption("mystack_compatibility_output")
    if not configured:
        return
    try:
        _reject_forbidden_imports(
            session.config.getoption("mystack_compatibility_forbidden_import")
        )
        document = collect_compatibility_items(session.items)
        write_collection(Path(configured), document)
    except CompatibilityCollectionError as error:
        raise pytest.UsageError(f"Mystack compatibility collection failed: {error}") from error


def _reject_forbidden_imports(packages: Iterable[str]) -> None:
    """Keep collection-only evidence isolated from optional heavyweight test clients."""

    normalized = sorted({package.strip() for package in packages if package.strip()})
    imported = [
        package
        for package in normalized
        if package in sys.modules or any(name.startswith(f"{package}.") for name in sys.modules)
    ]
    if imported:
        raise CompatibilityCollectionError(
            "collection-only evidence imported forbidden optional clients "
            f"packages={imported}; move those imports into the test body"
        )


def _validate_execution_marker(item: pytest.Item, payload: dict[str, Any]) -> None:
    profile = payload["profile"]
    expected = ExecutionKind(profile["execution"])
    actual_markers = {
        kind for kind in ExecutionKind if item.get_closest_marker(kind.value) is not None
    }
    if actual_markers != {expected}:
        names = sorted(value.value for value in actual_markers)
        raise CompatibilityCollectionError(
            "profile execution must match exactly one pytest marker "
            f"nodeid={item.nodeid} expected={expected.value} actual={names}"
        )


def _merge(grouped: dict[str, dict[str, Any]], nodeid: str, payload: dict[str, Any]) -> None:
    profile = payload["profile"]
    case_id = profile["id"]
    existing = grouped.get(case_id)
    if existing is None:
        grouped[case_id] = {
            "id": case_id,
            "profile": profile,
            "test_nodes": [nodeid],
            "scenario_ids": list(payload["scenario_ids"]),
            "operations": {
                service: list(names) for service, names in payload["operations"].items()
            },
            "capabilities": list(payload["capabilities"]),
            "support_claims": [payload["support"]],
        }
        return
    if existing["profile"] != profile:
        raise CompatibilityCollectionError(
            f"profile conflict for case_id={case_id!r} nodeid={nodeid}"
        )
    existing["test_nodes"].append(nodeid)
    existing["scenario_ids"] = sorted(set(existing["scenario_ids"]) | set(payload["scenario_ids"]))
    existing["capabilities"] = sorted(set(existing["capabilities"]) | set(payload["capabilities"]))
    existing["support_claims"] = sorted(set(existing["support_claims"]) | {payload["support"]})
    for service, names in payload["operations"].items():
        existing["operations"][service] = sorted(
            set(existing["operations"].get(service, [])) | set(names)
        )
    existing["operations"] = dict(sorted(existing["operations"].items()))
    existing["test_nodes"].sort()
