"""Contracts for the manifest-driven interoperability matrix.

Official shared-matrix reference:
https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
"""

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
    MatrixCompiler,
    compile_manifest,
)
from scripts.run_compatibility_case import (
    CaseSelectionError,
    CompiledCaseRepository,
    IsolatedCaseRunner,
    TimeoutConfiguration,
)

ROOT = Path(__file__).parents[1]


def _document() -> dict:
    return yaml.safe_load(DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def _compile_mutation(tmp_path: Path, mutation) -> dict:
    document = _document()
    mutation(document)
    manifest = tmp_path / "cases.yaml"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return compile_manifest(manifest)


def test_committed_generated_matrix_is_current_and_lossless() -> None:
    compiled = compile_manifest(DEFAULT_MANIFEST)
    committed = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert compiled == committed

    cases = {case["id"]: case for case in compiled["cases"]}
    boto = cases["boto3-botocore-1.43.66-contract"]
    emr = cases["emr-7.8.0-spark-3.5.4"]
    glue = cases["glue-5.0-spark-3.5.4-hive-iceberg-1.7.1"]
    assert boto["compatibility_profiles"]["boto3-control-plane"]["versions"] == {
        "boto3": "1.43.66",
        "botocore": "1.43.66",
    }
    assert emr["runtime"]["release_label"] == "emr-7.8.0"
    assert emr["runtime"]["spark_version"] == "3.5.4"
    assert glue["runtime"] == {
        "config_profile": "glue-5.0",
        "glue_version": "5.0",
        "iceberg_version": "1.7.1",
        "java_version": "17",
        "kind": "glue",
        "python_version": "3.11",
        "source": "glue-5.0",
        "spark_version": "3.5.4",
    }
    assert all(len(case["evidence_sha256"]) == 64 for case in compiled["cases"])
    assert len(compiled["acceptance"]["evidence_sha256"]) == 64
    acceptance = compiled["acceptance"]
    covered_cases = {
        case_id for area in acceptance["areas"].values() for case_id in area["case_ids"]
    }
    covered_scenarios = {
        scenario_id for area in acceptance["areas"].values() for scenario_id in area["scenario_ids"]
    }
    required = [case for case in compiled["cases"] if case["release_blocking"]]
    assert covered_cases == {case["id"] for case in required}
    assert covered_scenarios == {
        scenario_id for case in required for scenario_id in case["scenario"]["scenario_ids"]
    }


def test_same_contract_case_adds_an_actions_entry_without_cross_product(tmp_path: Path) -> None:
    baseline = compile_manifest(DEFAULT_MANIFEST)

    def add_case(document: dict) -> None:
        case = copy.deepcopy(document["cases"][0])
        case["id"] = "boto3-botocore-1.43.66-contract-second-explicit-case"
        document["cases"].append(case)
        document["acceptance"]["areas"]["glue-control-plane-errors"]["case_ids"].append(case["id"])

    changed = _compile_mutation(tmp_path, add_case)
    before = baseline["github_matrices"]["required_contract"]["include"]
    after = changed["github_matrices"]["required_contract"]["include"]
    assert len(after) == len(before) + 1
    assert {entry["case_id"] for entry in after} - {entry["case_id"] for entry in before} == {
        "boto3-botocore-1.43.66-contract-second-explicit-case"
    }
    assert len(changed["cases"]) == len(baseline["cases"]) + 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["cases"][0].update({"surprise": True}), "schema mismatch"),
        (
            lambda value: value["artifacts"]["boto3-1.43.66"].update(
                {"immutable_uri": "https://example.invalid/latest/boto3-1.43.66.whl"}
            ),
            "mutable or unversioned artifact",
        ),
        (
            lambda value: value["artifacts"]["boto3-1.43.66"].update(
                {"digest": "sha256:not-a-digest"}
            ),
            "invalid artifact digest",
        ),
        (
            lambda value: value["artifacts"]["boto3-1.43.66"].update(
                {"digest": f"sha256:{'0' * 64}"}
            ),
            "Python artifact/uv.lock drift",
        ),
        (
            lambda value: value["cases"][0].update({"runner_adapter": "missing-adapter"}),
            "unknown reference",
        ),
        (
            lambda value: value["runtime_profiles"]["emr-7.8.0-spark-3.5.4"].update(
                {"spark_version": "3.5.5"}
            ),
            "runtime/config drift",
        ),
        (
            lambda value: value["cases"][0].update({"artifacts": ["botocore-1.43.66"]}),
            "profile version has no exact case artifact",
        ),
        (
            lambda value: value["acceptance"]["areas"]["spark-hive"]["scenario_ids"].pop(),
            "scenario acceptance coverage drift",
        ),
        (
            lambda value: value["acceptance"]["areas"]["spark-hive"]["evidence_paths"].append(
                "missing/release-evidence.md"
            ),
            "missing or unsafe acceptance evidence",
        ),
    ],
)
def test_pretest_validation_rejects_drift(tmp_path: Path, mutation, message: str) -> None:
    with pytest.raises(ManifestError, match=message):
        _compile_mutation(tmp_path, mutation)


def test_duplicate_yaml_keys_and_case_ids_are_rejected(tmp_path: Path) -> None:
    duplicate_key = tmp_path / "duplicate-key.yaml"
    duplicate_key.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate YAML key"):
        compile_manifest(duplicate_key)

    def duplicate_case(document: dict) -> None:
        document["cases"].append(copy.deepcopy(document["cases"][0]))

    with pytest.raises(ManifestError, match="duplicate case id"):
        _compile_mutation(tmp_path, duplicate_case)


def test_each_lane_has_an_explicit_non_cross_product_case_matrix() -> None:
    compiled = compile_manifest(DEFAULT_MANIFEST)
    assert set(compiled["github_matrices"]) == set(MatrixCompiler.MATRIX_KEYS)
    assert compiled["lanes"]["required"]["release_blocking"] is True
    assert compiled["lanes"]["preview"]["release_blocking"] is False
    assert compiled["lanes"]["nightly"]["release_blocking"] is False
    matrix_ids = {
        entry["case_id"]
        for matrix in compiled["github_matrices"].values()
        for entry in matrix["include"]
    }
    assert matrix_ids == {case["id"] for case in compiled["cases"]}


def test_release_workflow_preserves_compiled_acceptance_evidence() -> None:
    workflow = (ROOT / ".github/workflows/container-publish.yml").read_text(encoding="utf-8")

    assert "Preserve release-blocking acceptance and diagnostics" in workflow
    for path in (
        "contracts/compatibility-matrix.generated.json",
        "contracts/api-coverage.json",
        "contracts/glue-error-conditions.yaml",
        "docs/compatibility/release-acceptance.generated.md",
        "docs/compatibility/release-acceptance.ko.generated.md",
    ):
        assert path in workflow


def test_isolated_runner_uses_generated_nodes_and_configured_timeout() -> None:
    case = CompiledCaseRepository(DEFAULT_OUTPUT).get("boto3-botocore-1.43.66-contract")
    runner = IsolatedCaseRunner(
        root=ROOT,
        timeout_configuration=TimeoutConfiguration(ROOT / "config/mystack.yaml"),
    )
    command, timeout = runner.command(case)
    assert command[:3] == ["uv", "run", "pytest"]
    nodes = command[3 : command.index("-m")]
    assert any(node.startswith("emr/tests/test_boto3_contract.py::") for node in nodes)
    assert any(node.startswith("glue/tests/test_boto3_contract.py::") for node in nodes)
    assert all("test_ui" not in node for node in nodes)
    assert command[command.index("--timeout") + 1] == str(timeout)
    assert timeout == 120


def test_isolated_runner_rejects_an_unknown_generated_adapter() -> None:
    case = copy.deepcopy(CompiledCaseRepository(DEFAULT_OUTPUT).all()[0])
    case["runner"]["kind"] = "shell"
    runner = IsolatedCaseRunner(
        root=ROOT,
        timeout_configuration=TimeoutConfiguration(ROOT / "config/mystack.yaml"),
    )
    with pytest.raises(CaseSelectionError, match="unknown generated runner"):
        runner.command(case)
