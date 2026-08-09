"""Render safe, human-readable CI evidence from JUnit XML.

The renderer intentionally has no GitHub, registry, or test-runner dependency. Test runners write
standard JUnit XML, this module turns it into a small static HTML page and a GitHub Job Summary, and
the workflow decides how long to retain the resulting artifact. Keeping those responsibilities
separate means a failed test report cannot become a second quality gate.

Sources:
- pytest JUnit XML: https://docs.pytest.org/en/stable/how-to/output.html
- Vitest reporters: https://vitest.dev/guide/reporters
- GitHub step summaries and annotations:
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Spark's CI uploads JUnit XML, publishes a summary, and keeps verbose logs failure-only:
  https://github.com/apache/spark/blob/master/.github/workflows/build_and_test.yml
- Trino separates always-available test reports from failure diagnostics and annotates the job:
  https://github.com/trinodb/trino/blob/master/.github/actions/process-test-results/action.yml
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import xml.etree.ElementTree as element_tree
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ReportStatus(StrEnum):
    """The stable status exposed by a rendered report."""

    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class CaseStatus(StrEnum):
    """The normalized JUnit case outcome."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class JUnitInput:
    """One labeled JUnit XML file selected by a workflow."""

    label: str
    path: Path


@dataclass(frozen=True)
class TestCase:
    """One normalized test case with a short, safe diagnostic."""

    suite: str
    name: str
    status: CaseStatus
    duration_seconds: float
    message: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.suite}::{self.name}" if self.suite else self.name


@dataclass(frozen=True)
class SuiteResult:
    """A runner-owned result file and its normalized test cases."""

    source: JUnitInput
    cases: tuple[TestCase, ...]
    problem: str = ""

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(case.status is CaseStatus.PASSED for case in self.cases)

    @property
    def failed(self) -> int:
        return sum(case.status is CaseStatus.FAILED for case in self.cases)

    @property
    def errors(self) -> int:
        return sum(case.status is CaseStatus.ERROR for case in self.cases)

    @property
    def skipped(self) -> int:
        return sum(case.status is CaseStatus.SKIPPED for case in self.cases)

    @property
    def duration_seconds(self) -> float:
        return sum(case.duration_seconds for case in self.cases)


@dataclass(frozen=True)
class Report:
    """The complete, runner-neutral CI evidence model."""

    title: str
    suites: tuple[SuiteResult, ...]

    @property
    def status(self) -> ReportStatus:
        if any(suite.problem for suite in self.suites):
            return ReportStatus.INCOMPLETE
        if any(suite.failed or suite.errors for suite in self.suites):
            return ReportStatus.FAILED
        return ReportStatus.PASSED

    @property
    def total(self) -> int:
        return sum(suite.total for suite in self.suites)

    @property
    def passed(self) -> int:
        return sum(suite.passed for suite in self.suites)

    @property
    def failed(self) -> int:
        return sum(suite.failed for suite in self.suites)

    @property
    def errors(self) -> int:
        return sum(suite.errors for suite in self.suites)

    @property
    def skipped(self) -> int:
        return sum(suite.skipped for suite in self.suites)

    @property
    def duration_seconds(self) -> float:
        return sum(suite.duration_seconds for suite in self.suites)

    @property
    def failed_cases(self) -> tuple[TestCase, ...]:
        return tuple(
            case
            for suite in self.suites
            for case in suite.cases
            if case.status in {CaseStatus.FAILED, CaseStatus.ERROR}
        )


class JUnitReader:
    """Read the subset of JUnit XML that pytest and Vitest both emit."""

    _sensitive_assignment = re.compile(
        r"(?i)\b(token|password|secret|api[_-]?key|authorization)\b\s*[:=]\s*[^\s,;]+"
    )
    _credential_url = re.compile(r"://[^/\s:@]+:[^@\s/]+@")

    def read(self, source: JUnitInput) -> SuiteResult:
        if not source.path.exists():
            return SuiteResult(source=source, cases=(), problem="JUnit XML was not produced")
        try:
            root = element_tree.parse(source.path).getroot()
        except element_tree.ParseError as error:
            return SuiteResult(
                source=source,
                cases=(),
                problem=f"JUnit XML could not be parsed: {self._single_line(str(error))}",
            )

        cases = tuple(self._test_cases(root, fallback_suite=source.label))
        if not cases:
            return SuiteResult(source=source, cases=(), problem="JUnit XML contains no test cases")
        return SuiteResult(source=source, cases=cases)

    def _test_cases(self, root: element_tree.Element, *, fallback_suite: str) -> Iterable[TestCase]:
        for node in root.iter():
            if self._local_name(node.tag) != "testcase":
                continue
            suite = node.attrib.get("classname", fallback_suite)
            name = node.attrib.get("name", "unnamed test")
            status, message = self._case_status(node)
            yield TestCase(
                suite=self._single_line(suite),
                name=self._single_line(name),
                status=status,
                duration_seconds=self._duration(node.attrib.get("time")),
                message=message,
            )

    def _case_status(self, node: element_tree.Element) -> tuple[CaseStatus, str]:
        for child in node:
            tag = self._local_name(child.tag)
            if tag == "failure":
                return CaseStatus.FAILED, self._message(child)
            if tag == "error":
                return CaseStatus.ERROR, self._message(child)
            if tag == "skipped":
                return CaseStatus.SKIPPED, self._message(child)
        return CaseStatus.PASSED, ""

    def _message(self, node: element_tree.Element) -> str:
        raw = node.attrib.get("message") or node.text or ""
        return self._redact(self._single_line(raw))[:500]

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1]

    @staticmethod
    def _duration(raw: str | None) -> float:
        try:
            return max(0.0, float(raw or "0"))
        except ValueError:
            return 0.0

    @staticmethod
    def _single_line(value: str) -> str:
        return " ".join(value.split())

    def _redact(self, value: str) -> str:
        value = self._sensitive_assignment.sub(r"\1=<redacted>", value)
        return self._credential_url.sub("://<redacted>@", value)


class ReportRenderer:
    """Render an immutable report model without reading files or mutating a workflow."""

    def markdown(self, report: Report, *, artifact_name: str) -> str:
        lines = [
            f"## {self._markdown(report.title)}",
            "",
            f"**Result:** `{report.status}` · {report.passed}/{report.total} passed · "
            f"{report.failed} failed · {report.errors} errors · {report.skipped} skipped · "
            f"{report.duration_seconds:.2f}s",
            "",
            "| Runner | Total | Passed | Failed | Errors | Skipped | Duration |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for suite in report.suites:
            row = (
                f"| {self._markdown(suite.source.label)} | {suite.total} | {suite.passed} | "
                f"{suite.failed} | {suite.errors} | {suite.skipped} | "
                f"{suite.duration_seconds:.2f}s |"
            )
            lines.append(row)
            if suite.problem:
                lines.append(f"| ↳ report | — | — | — | — | — | {self._markdown(suite.problem)} |")
        if report.failed_cases:
            lines.extend(["", "### Failed tests", ""])
            for case in report.failed_cases:
                message = f": {self._markdown(case.message)}" if case.message else ""
                lines.append(f"- `{case.status}` {self._markdown(case.display_name)}{message}")
        artifact_url = self._artifact_url()
        if artifact_url:
            lines.extend(
                [
                    "",
                    f"Download `{self._markdown(artifact_name)}` from the "
                    f"[workflow artifacts]({artifact_url}).",
                ]
            )
        return "\n".join(lines) + "\n"

    def html(self, report: Report, *, artifact_name: str) -> str:
        status = report.status
        sections = "\n".join(self._suite_html(suite) for suite in report.suites)
        artifact = ""
        artifact_url = self._artifact_url()
        if artifact_url:
            artifact = (
                f'<p class="artifact">Download <code>{html.escape(artifact_name)}</code> from '
                f'<a href="{html.escape(artifact_url, quote=True)}">workflow artifacts</a>.</p>'
            )
        status_markup = f'<span class="status {status}">{status}</span>'
        summary = (
            f"{status_markup} {report.passed}/{report.total} passed · "
            f"{report.failed} failed · {report.errors} errors · {report.skipped} skipped · "
            f"{report.duration_seconds:.2f}s"
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(report.title)} · Mystack CI</title>
  <style>
    :root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ max-width: 72rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #8b949e; padding: .45rem .6rem; text-align: left;
      vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    .status {{ display: inline-block; border-radius: 999px; padding: .2rem .6rem;
      font-weight: 700; }}
    .passed {{ background: #dafbe1; color: #116329; }}
    .failed, .error {{ background: #ffebe9; color: #cf222e; }}
    .incomplete {{ background: #fff8c5; color: #9a6700; }}
    .skipped {{ color: #57606a; }}
    code, pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    details {{ margin: .5rem 0; }}
    .artifact {{ margin-top: 2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(report.title)}</h1>
    <p>{summary}</p>
  </header>
  <table>
    <thead><tr><th>Runner</th><th>Total</th><th>Passed</th><th>Failed</th><th>Errors</th><th>Skipped</th><th>Duration</th></tr></thead>
    <tbody>{sections}</tbody>
  </table>
  {artifact}
</body>
</html>
"""

    def annotations(self, report: Report, *, maximum: int) -> str:
        lines: list[str] = []
        for suite in report.suites:
            if suite.problem:
                lines.append(
                    self._workflow_command(
                        "error",
                        title=f"{suite.source.label} JUnit report",
                        message=suite.problem,
                    )
                )
        for case in report.failed_cases[:maximum]:
            lines.append(
                self._workflow_command(
                    "error",
                    title=f"{case.status}: {case.display_name}",
                    message=case.message or "Test failed; inspect the static HTML report.",
                )
            )
        omitted = len(report.failed_cases) - maximum
        if omitted > 0:
            lines.append(
                self._workflow_command(
                    "warning",
                    title="JUnit annotation limit",
                    message=f"{omitted} additional failed tests are listed in the HTML report.",
                )
            )
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _markdown(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("\n", " ")
        for character in ("|", "`", "[", "]", "(", ")"):
            escaped = escaped.replace(character, f"\\{character}")
        return escaped

    @staticmethod
    def _workflow_command(level: str, *, title: str, message: str) -> str:
        def escape_data(value: str) -> str:
            return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

        def escape_property(value: str) -> str:
            return escape_data(value).replace(":", "%3A").replace(",", "%2C")

        return f"::{level} title={escape_property(title)}::{escape_data(message)}"

    @staticmethod
    def _artifact_url() -> str:
        server = os.environ.get("GITHUB_SERVER_URL")
        repository = os.environ.get("GITHUB_REPOSITORY")
        run_id = os.environ.get("GITHUB_RUN_ID")
        if not (server and server.startswith("https://") and repository and run_id):
            return ""
        return f"{server}/{repository}/actions/runs/{run_id}#artifacts"

    def _suite_html(self, suite: SuiteResult) -> str:
        row = (
            f"<tr><td>{html.escape(suite.source.label)}</td><td>{suite.total}</td>"
            f"<td>{suite.passed}</td><td>{suite.failed}</td><td>{suite.errors}</td>"
            f"<td>{suite.skipped}</td><td>{suite.duration_seconds:.2f}s</td></tr>"
        )
        details: list[str] = []
        if suite.problem:
            details.append(
                "<details open><summary>Report problem</summary><p>"
                f"{html.escape(suite.problem)}</p></details>"
            )
        for case in suite.cases:
            if case.status not in {CaseStatus.FAILED, CaseStatus.ERROR}:
                continue
            message = html.escape(case.message or "No JUnit failure message was supplied.")
            details.append(
                f'<details><summary><span class="{case.status}">{case.status}</span> '
                f"{html.escape(case.display_name)}</summary><pre>{message}</pre></details>"
            )
        if not details:
            return row
        return row + (
            f'<tr><td colspan="7"><strong>{html.escape(suite.source.label)} details</strong>'
            + "".join(details)
            + "</td></tr>"
        )


class ReportWriter:
    """Own the small report artifact layout selected by the workflow."""

    def __init__(
        self, reader: JUnitReader | None = None, renderer: ReportRenderer | None = None
    ) -> None:
        self._reader = reader or JUnitReader()
        self._renderer = renderer or ReportRenderer()

    def write(
        self,
        *,
        title: str,
        sources: Iterable[JUnitInput],
        output_dir: Path,
        artifact_name: str,
        maximum_annotations: int,
    ) -> Report:
        report = Report(title=title, suites=tuple(self._reader.read(source) for source in sources))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text(
            self._renderer.html(report, artifact_name=artifact_name), encoding="utf-8"
        )
        (output_dir / "summary.md").write_text(
            self._renderer.markdown(report, artifact_name=artifact_name), encoding="utf-8"
        )
        (output_dir / "github-annotations.txt").write_text(
            self._renderer.annotations(report, maximum=maximum_annotations), encoding="utf-8"
        )
        return report


def parse_input(value: str) -> JUnitInput:
    """Parse the explicit `label=path` workflow input without guessing a runner name."""

    label, separator, raw_path = value.partition("=")
    if not separator or not label.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("JUnit input must have the form label=path")
    return JUnitInput(label=label.strip(), path=Path(raw_path.strip()))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--input", action="append", type=parse_input, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--max-annotations", type=int, default=20)
    parser.add_argument("--emit-github-annotations", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.max_annotations <= 0:
        parser.error("--max-annotations must be positive")
    return arguments


def main(argv: list[str] | None = None) -> None:
    arguments = parse_args(argv)
    report = ReportWriter().write(
        title=arguments.title,
        sources=arguments.input,
        output_dir=arguments.output_dir,
        artifact_name=arguments.artifact_name,
        maximum_annotations=arguments.max_annotations,
    )
    print(
        "event=ci.test_report.write "
        f"status={report.status} total={report.total} failed={report.failed} "
        f"errors={report.errors} "
        f"output_dir={arguments.output_dir}"
    )
    if arguments.emit_github_annotations:
        annotations = arguments.output_dir / "github-annotations.txt"
        sys.stdout.write(annotations.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
