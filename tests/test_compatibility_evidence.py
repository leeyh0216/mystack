"""Contracts for pytest-declared compatibility evidence.

References:
- https://docs.pytest.org/en/stable/how-to/usage.html
- https://docs.pytest.org/en/stable/how-to/mark.html
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.compatibility_evidence import (
    DEFAULT_ENGLISH,
    DEFAULT_KOREAN,
    DEFAULT_OUTPUT,
    EvidenceCompilationError,
    EvidenceCompiler,
    GeneratedArtifacts,
    assert_legacy_parity,
    collect_annotations,
)
from test_support.compatibility import CompatibilityProfile, ExecutionKind, Lane
from test_support.compatibility_plugin import (
    CompatibilityCollectionError,
    _reject_forbidden_imports,
    collect_compatibility_items,
)

ROOT = Path(__file__).parents[1]


class _Marker:
    """Minimal pytest-marker shape for collector unit contracts."""

    args: tuple[object, ...] = ()

    def __init__(self, kwargs: dict[str, object]) -> None:
        self.kwargs = kwargs


class _Item:
    """Minimal pytest-item shape; no pytest test body or fixture is invoked."""

    def __init__(self, nodeid: str, *, marker: _Marker, execution_marker: str | None) -> None:
        self.nodeid = nodeid
        self._marker = marker
        self._execution_marker = execution_marker

    def iter_markers(self, name: str) -> tuple[_Marker, ...]:
        return (self._marker,) if name == "mystack_compatibility" else ()

    def get_closest_marker(self, name: str) -> _Marker | None:
        return self._marker if name == self._execution_marker else None


def _profile() -> CompatibilityProfile:
    return CompatibilityProfile(
        id="synthetic-contract",
        title_en="Synthetic collection contract",
        title_ko="합성 collection 계약",
        client="synthetic-client",
        versions={"synthetic-client": "1.0.0"},
        runtime_profile="python-3.11",
        runtime_kind="python",
        python_version="3.11",
        lane=Lane.PREVIEW,
        execution=ExecutionKind.CONTRACT,
        expected_duration_minutes=1,
        reference_urls=("https://docs.pytest.org/en/stable/how-to/mark.html",),
    )


def _payload() -> dict[str, object]:
    return {
        "profile": _profile().primitive(),
        "scenario_ids": ["synthetic-scenario"],
        "operations": {},
        "capabilities": [],
        "support": "verified",
    }


def test_collector_rejects_annotation_without_matching_execution_marker() -> None:
    item = _Item(
        "tests/test_synthetic.py::test_missing_contract_marker",
        marker=_Marker(_payload()),
        execution_marker=None,
    )

    with pytest.raises(CompatibilityCollectionError, match="profile execution"):
        collect_compatibility_items([item])


def test_collection_rejects_optional_heavy_client_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """A future module-level awswrangler/pyarrow import cannot silently slow collection."""

    monkeypatch.setitem(sys.modules, "awswrangler", object())

    with pytest.raises(CompatibilityCollectionError, match="forbidden optional clients"):
        _reject_forbidden_imports(["awswrangler", "pyarrow"])


def test_pytest_collection_writes_evidence_without_executing_test_body(tmp_path: Path) -> None:
    """`--collect-only` resolves the marker but succeeds despite an intentionally failing body."""

    test_module = tmp_path / "test_collection_only.py"
    test_module.write_text(
        """
import pytest

from test_support.compatibility import (
    CompatibilityProfile,
    ExecutionKind,
    Lane,
    compatibility_evidence,
)

PROFILE = CompatibilityProfile(
    id="collection-only-sentinel",
    title_en="Collection-only sentinel",
    title_ko="collection 전용 sentinel",
    client="synthetic-client",
    versions={"synthetic-client": "1.0.0"},
    runtime_profile="python-3.11",
    runtime_kind="python",
    python_version="3.11",
    lane=Lane.PREVIEW,
    execution=ExecutionKind.CONTRACT,
    expected_duration_minutes=1,
    reference_urls=("https://docs.pytest.org/en/stable/how-to/usage.html",),
)


@pytest.mark.contract
@compatibility_evidence(PROFILE, scenario_ids=("collection-only-sentinel",))
def test_body_must_not_execute():
    raise AssertionError("test body executed")
""",
        encoding="utf-8",
    )
    output = tmp_path / "evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "test_support.compatibility_plugin",
            "--mystack-compatibility-output",
            str(output),
            str(test_module),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["cases"][0]["id"] == "collection-only-sentinel"
    assert document["cases"][0]["test_nodes"][0].endswith("::test_body_must_not_execute")


@pytest.fixture(scope="module")
def collected_evidence() -> dict[str, Any]:
    """Run the production collection boundary once for the focused evidence contracts."""

    return collect_annotations()


def test_current_annotations_compile_match_legacy_and_generated_artifacts(
    collected_evidence: dict[str, Any],
) -> None:
    compiled = EvidenceCompiler().compile(collected_evidence)

    assert {case["id"] for case in compiled["cases"]} == {
        "awswrangler-3.17.0-glue-s3",
        "boto3-botocore-1.43.66-contract",
        "boto3-botocore-1.43.66-public-proxy",
        "emr-7.8.0-spark-3.5.4",
        "glue-5.0-spark-3.5.4-hive-iceberg-1.7.1",
    }
    assert_legacy_parity(compiled)
    artifacts = GeneratedArtifacts(DEFAULT_OUTPUT, DEFAULT_ENGLISH, DEFAULT_KOREAN)
    artifacts.check(artifacts.expected(compiled))


def test_compiler_requires_annotation_evidence_for_every_supported_api(
    collected_evidence: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(collected_evidence)
    for case in mutated["cases"]:
        operations = case["operations"]
        if "glue" in operations:
            operations["glue"] = [
                operation for operation in operations["glue"] if operation != "GetTableOptimizer"
            ]

    with pytest.raises(EvidenceCompilationError, match="lacks annotated evidence"):
        EvidenceCompiler().compile(mutated)


def test_ci_and_release_jobs_select_test_declared_generated_evidence() -> None:
    workflow_paths = (
        ROOT / ".github/workflows/ci.yml",
        ROOT / ".github/workflows/e2e.yml",
        ROOT / ".github/workflows/container-publish.yml",
    )
    for path in workflow_paths:
        workflow = path.read_text(encoding="utf-8")
        assert "contracts/compatibility-evidence.generated.json" in workflow
        assert "compatibility-evidence-check" in workflow
