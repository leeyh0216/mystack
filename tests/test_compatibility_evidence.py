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
import yaml

import scripts.compatibility.compatibility_evidence as compatibility_evidence_module
from scripts.compatibility.compatibility_evidence import (
    DEFAULT_ENGLISH,
    DEFAULT_KOREAN,
    DEFAULT_OUTPUT,
    EvidenceCompilationError,
    EvidenceCompiler,
    GeneratedArtifacts,
    collect_annotations,
)
from tests.support.compatibility import CompatibilityProfile, ExecutionKind, Lane
from tests.support.compatibility_plugin import (
    CompatibilityCollectionError,
    _reject_forbidden_imports,
    collect_compatibility_items,
)

ROOT = Path(__file__).parents[1]


def _config_with_collection_timeout(tmp_path: Path, timeout: float) -> Path:
    document = yaml.safe_load((ROOT / "config/runtime/mystack.yaml").read_text(encoding="utf-8"))
    document["tests"]["compatibility_collection_timeout_seconds"] = timeout
    path = tmp_path / "mystack.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


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


def test_collector_rejects_conflicting_duplicate_case_ids() -> None:
    """One profile ID can span tests only when every profile field is identical."""

    first = _payload()
    second = copy.deepcopy(first)
    second["profile"]["client"] = "other-client"  # type: ignore[index]
    items = (
        _Item(
            "tests/test_synthetic.py::test_first",
            marker=_Marker(first),
            execution_marker="contract",
        ),
        _Item(
            "tests/test_synthetic.py::test_second",
            marker=_Marker(second),
            execution_marker="contract",
        ),
    )

    with pytest.raises(CompatibilityCollectionError, match="profile conflict"):
        collect_compatibility_items(items)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("lane", "untracked", "unknown lane"),
        ("runtime_kind", "lambda", "runtime_kind"),
        ("client", "", "client"),
    ),
)
def test_collector_rejects_invalid_profile_metadata(field: str, value: str, message: str) -> None:
    payload = _payload()
    payload["profile"][field] = value  # type: ignore[index]
    item = _Item(
        "tests/test_synthetic.py::test_invalid_profile",
        marker=_Marker(payload),
        execution_marker="contract",
    )

    with pytest.raises(CompatibilityCollectionError, match=message):
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

from tests.support.compatibility import (
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
            "tests.support.compatibility_plugin",
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


def test_collection_uses_the_selected_file_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _config_with_collection_timeout(tmp_path, 7.5)
    monkeypatch.delenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(
        compatibility_evidence_module,
        "_annotated_test_paths",
        lambda: ["tests/test_synthetic.py"],
    )
    captured: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = kwargs["timeout"]
        output = Path(command[command.index("--mystack-compatibility-output") + 1])
        output.write_text('{"cases": []}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(compatibility_evidence_module.subprocess, "run", run)

    assert collect_annotations(config_path=config) == {"cases": []}
    assert captured["timeout"] == 7.5


def test_collection_uses_the_effective_environment_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _config_with_collection_timeout(tmp_path, 7.5)
    monkeypatch.setenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", "11")
    monkeypatch.setattr(
        compatibility_evidence_module,
        "_annotated_test_paths",
        lambda: ["tests/test_synthetic.py"],
    )
    captured: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = kwargs["timeout"]
        output = Path(command[command.index("--mystack-compatibility-output") + 1])
        output.write_text('{"cases": []}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(compatibility_evidence_module.subprocess, "run", run)

    assert collect_annotations(config_path=config) == {"cases": []}
    assert captured["timeout"] == 11.0


def test_collection_timeout_is_bounded_and_redacts_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = _config_with_collection_timeout(tmp_path, 3)
    monkeypatch.delenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(
        compatibility_evidence_module,
        "_annotated_test_paths",
        lambda: ["tests/test_synthetic.py"],
    )

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            kwargs["timeout"],
            output="AWS_SESSION_TOKEN=temporary-session-token",
            stderr="password: local-only-password",
        )

    monkeypatch.setattr(compatibility_evidence_module.subprocess, "run", run)

    with pytest.raises(EvidenceCompilationError, match="collection timed out"):
        collect_annotations(config_path=config)

    assert "temporary-session-token" not in caplog.text
    assert "local-only-password" not in caplog.text
    assert "AWS_SESSION_TOKEN=<redacted>" in caplog.text
    assert "password:<redacted>" in caplog.text


def test_collection_rejects_a_missing_or_non_positive_file_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _config_with_collection_timeout(tmp_path, 0)
    monkeypatch.delenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", raising=False)

    with pytest.raises(EvidenceCompilationError, match="compatibility_collection_timeout_seconds"):
        compatibility_evidence_module._collection_timeout_seconds(config)


@pytest.mark.parametrize(
    ("diagnostic", "secret", "expected"),
    (
        (
            "Authorization: Bearer super-secret-value",
            "super-secret-value",
            "Authorization:<redacted>",
        ),
        (
            "Authorization: AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE, Signature=signature-secret",
            "signature-secret",
            "Authorization:<redacted>",
        ),
        ("X-Amz-Signature=signature-secret", "signature-secret", "Signature=<redacted>"),
    ),
)
def test_collection_diagnostics_redact_authorization_and_signatures(
    diagnostic: str, secret: str, expected: str
) -> None:
    redacted = compatibility_evidence_module._tail(diagnostic)

    assert secret not in redacted
    assert expected in redacted


def test_cli_passes_the_selected_config_to_collection_and_compiler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "mystack.yaml"
    captured: dict[str, object] = {}

    class Compiler:
        def __init__(self, *, config_path: Path) -> None:
            captured["compiler_config"] = config_path

        def compile(self, collected: dict[str, object]) -> dict[str, object]:
            assert collected == {"collected": True}
            return {"compiled": True}

    def collect(*, config_path: Path) -> dict[str, object]:
        captured["collection_config"] = config_path
        return {"collected": True}

    monkeypatch.setattr(compatibility_evidence_module, "EvidenceCompiler", Compiler)
    monkeypatch.setattr(compatibility_evidence_module, "collect_annotations", collect)

    class Artifacts:
        def __init__(self, *_: object) -> None:
            pass

        def expected(self, compiled: dict[str, object]) -> dict[Path, str]:
            assert compiled == {"compiled": True}
            return {}

        def check(self, expected: dict[Path, str]) -> None:
            assert expected == {}

    monkeypatch.setattr(compatibility_evidence_module, "GeneratedArtifacts", Artifacts)
    monkeypatch.setattr(
        compatibility_evidence_module.sys,
        "argv",
        ["compatibility_evidence.py", "--check", "--config", str(config)],
    )

    assert compatibility_evidence_module.main() == 0
    assert captured == {"collection_config": config, "compiler_config": config}


@pytest.fixture(scope="module")
def collected_evidence() -> dict[str, Any]:
    """Run the production collection boundary once for the focused evidence contracts."""

    return collect_annotations()


def test_current_annotations_compile_and_match_generated_artifacts(
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
        assert "ci-artifacts/compatibility/compatibility-evidence.json" in workflow
        assert "compatibility-evidence-check" in workflow


def test_docker_e2e_uses_the_python_version_from_generated_case_evidence() -> None:
    workflow = (ROOT / ".github/workflows/e2e.yml").read_text(encoding="utf-8")
    start = workflow.index("  boto-spark-catalog-iceberg:")
    end = workflow.index("\n  console-accessibility:", start)
    docker_case_job = workflow[start:end]

    assert "python-version: ${{ matrix.python_version }}" in docker_case_job
    assert 'python-version: "3.11"' not in docker_case_job


def test_generated_artifacts_reject_stale_output(tmp_path: Path) -> None:
    artifacts = GeneratedArtifacts(
        tmp_path / "evidence.json",
        tmp_path / "evidence.md",
        tmp_path / "evidence.ko.md",
    )
    expected = {
        tmp_path / "evidence.json": "{}\n",
        tmp_path / "evidence.md": "# English\n",
        tmp_path / "evidence.ko.md": "# 한국어\n",
    }
    artifacts.write(expected)
    (tmp_path / "evidence.json").write_text('{"stale": true}\n', encoding="utf-8")

    with pytest.raises(EvidenceCompilationError, match="evidence drift"):
        artifacts.check(expected)
