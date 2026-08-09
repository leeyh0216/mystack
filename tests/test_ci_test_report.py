"""Contracts for static CI test evidence.

Sources:
- pytest JUnit XML: https://docs.pytest.org/en/stable/how-to/output.html
- GitHub step-summary and annotation workflow commands:
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ci_test_report import JUnitInput, ReportStatus, ReportWriter, parse_input

ROOT = Path(__file__).parents[1]


def test_writer_renders_safe_junit_summary_html_and_annotations(
    tmp_path: Path, monkeypatch
) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<testsuites>
  <testsuite name=\"unit\">
    <testcase classname=\"mystack.unit\" name=\"passes\" time=\"0.25\" />
    <testcase classname=\"mystack.unit\" name=\"&lt;script&gt;fails&lt;/script&gt;\" time=\"0.50\">
      <failure message=\"token=super-secret\">raw detail</failure>
    </testcase>
    <testcase classname=\"mystack.unit\" name=\"skips\" time=\"0.00\"><skipped /></testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repository")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")

    output = tmp_path / "report"
    report = ReportWriter().write(
        title="Python contracts",
        sources=[JUnitInput(label="Python 3.11", path=junit)],
        output_dir=output,
        artifact_name="python-3.11-test-report",
        maximum_annotations=20,
    )

    assert report.status is ReportStatus.FAILED
    assert (report.total, report.passed, report.failed, report.skipped) == (3, 1, 1, 1)
    assert report.failed_cases[0].message == "token=<redacted>"

    index = (output / "index.html").read_text(encoding="utf-8")
    summary = (output / "summary.md").read_text(encoding="utf-8")
    annotations = (output / "github-annotations.txt").read_text(encoding="utf-8")
    assert "&lt;script&gt;fails&lt;/script&gt;" in index
    assert "<script>fails</script>" not in index
    assert "token=&lt;redacted&gt;" in index
    assert "workflow artifacts" in summary
    assert "https://github.example/owner/repository/actions/runs/42#artifacts" in summary
    expected_annotation = (
        "::error title=failed%3A mystack.unit%3A%3A<script>fails</script>::token=<redacted>"
    )
    assert expected_annotation in annotations


def test_writer_marks_missing_junit_as_incomplete_without_hiding_the_result(tmp_path: Path) -> None:
    output = tmp_path / "report"

    report = ReportWriter().write(
        title="Compatibility case",
        sources=[JUnitInput(label="boto3 contract", path=tmp_path / "missing.xml")],
        output_dir=output,
        artifact_name="compatibility-test-report",
        maximum_annotations=20,
    )

    assert report.status is ReportStatus.INCOMPLETE
    assert "JUnit XML was not produced" in (output / "summary.md").read_text(encoding="utf-8")
    assert "::error title=boto3 contract JUnit report::JUnit XML was not produced" in (
        output / "github-annotations.txt"
    ).read_text(encoding="utf-8")


def test_input_requires_an_explicit_runner_label() -> None:
    parsed = parse_input("frontend=ci-artifacts/frontend/junit.xml")

    assert parsed == JUnitInput(label="frontend", path=Path("ci-artifacts/frontend/junit.xml"))


def test_ci_uses_the_shared_reporter_and_failure_only_diagnostics() -> None:
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    e2e_workflow = (ROOT / ".github/workflows/e2e.yml").read_text(encoding="utf-8")
    action = (ROOT / ".github/actions/publish-test-report/action.yml").read_text(encoding="utf-8")

    assert ci_workflow.count("uses: ./.github/actions/publish-test-report") == 3
    assert e2e_workflow.count("uses: ./.github/actions/publish-test-report") == 3
    assert "MYSTACK_TEST_REPORT_RETENTION_DAYS" in ci_workflow
    assert "MYSTACK_FAILURE_DIAGNOSTIC_RETENTION_DAYS" in e2e_workflow
    assert "name: python-${{ matrix.python-version }}-failure-diagnostics" in ci_workflow
    assert "name: e2e-${{ matrix.case_id }}-failure-diagnostics" in e2e_workflow
    assert "if: failure()" in e2e_workflow
    assert "--emit-github-annotations" in action
    assert 'cat "$OUTPUT_DIR/summary.md" >>"$GITHUB_STEP_SUMMARY"' in action


def test_frontend_timeout_remains_owned_by_the_environment_aware_vitest_config() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    vitest_config = (ROOT / "vitest.config.ts").read_text(encoding="utf-8")

    assert package["scripts"]["frontend:test"] == "vitest run"
    assert "MYSTACK_FRONTEND_TEST_TIMEOUT_MS" in vitest_config
    assert "testTimeout: configuredTimeout" in vitest_config
    assert "hookTimeout: configuredTimeout" in vitest_config
