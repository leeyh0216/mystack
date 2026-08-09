"""Contracts for generated, annotation-backed interoperability evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from scripts.compatibility_matrix import (
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT,
    ManifestError,
    compile_manifest,
)
from scripts.run_compatibility_case import (
    CaseSelectionError,
    CompiledCaseRepository,
    IsolatedCaseRunner,
    TimeoutConfiguration,
)

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "contracts/compatibility-evidence.generated.json"


def test_committed_generated_matrix_is_current_and_lossless() -> None:
    compiled = compile_manifest(DEFAULT_MANIFEST)
    assert compiled == json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert compiled["generated_from"] == {
        "annotated_evidence": "contracts/compatibility-evidence.generated.json",
        "scope_policy": "contracts/compatibility-scope-policy.yaml",
    }
    assert {case["id"] for case in compiled["cases"]} == {
        entry["case_id"]
        for matrix in compiled["github_matrices"].values()
        for entry in matrix["include"]
    }


def test_scope_policy_must_cover_all_required_annotation_evidence(tmp_path: Path) -> None:
    policy = yaml.safe_load(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    policy["acceptance"]["areas"]["emr-pyspark-s3"]["scenario_ids"].pop()
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    with pytest.raises(ManifestError, match="scenario acceptance coverage drift"):
        compile_manifest(policy_path, evidence_path=EVIDENCE)


def test_scope_policy_rejects_unknown_source(tmp_path: Path) -> None:
    policy = yaml.safe_load(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    policy["acceptance"]["areas"]["emr-pyspark-s3"]["official_sources"].append("missing")
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    with pytest.raises(ManifestError, match="unknown acceptance source"):
        compile_manifest(policy_path, evidence_path=EVIDENCE)


def test_isolated_runner_uses_generated_nodes_and_configured_timeout() -> None:
    case = CompiledCaseRepository(DEFAULT_OUTPUT).get("boto3-botocore-1.43.66-contract")
    runner = IsolatedCaseRunner(
        root=ROOT, timeout_configuration=TimeoutConfiguration(ROOT / "config/mystack.yaml")
    )
    command, timeout = runner.command(case)
    assert command[:3] == ["uv", "run", "pytest"]
    assert any(node.startswith("emr/tests/test_boto3_contract.py::") for node in command)
    assert timeout == 120


def test_isolated_runner_rejects_unknown_generated_adapter() -> None:
    case = copy.deepcopy(CompiledCaseRepository(DEFAULT_OUTPUT).all()[0])
    case["runner"]["kind"] = "shell"
    runner = IsolatedCaseRunner(
        root=ROOT, timeout_configuration=TimeoutConfiguration(ROOT / "config/mystack.yaml")
    )
    with pytest.raises(CaseSelectionError, match="unknown generated runner"):
        runner.command(case)
