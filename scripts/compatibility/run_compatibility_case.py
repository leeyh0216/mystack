"""Run one compiled compatibility case in an isolated pytest process.

The runner consumes generated test-declared evidence rather than interpreting authoring metadata.
This keeps GitHub Actions and local execution on the same reviewed contract.

Official pytest invocation reference: https://docs.pytest.org/en/stable/how-to/usage.html
JUnit XML output reference: https://docs.pytest.org/en/stable/how-to/output.html
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.compatibility.artifacts import EVIDENCE_JSON  # noqa: E402

LOGGER = logging.getLogger("mystack.compatibility.runner")
APPROVED_RUNNERS = {
    "pytest": ("contract", ["uv", "run", "pytest"]),
    "docker-pytest": ("e2e", ["uv", "run", "pytest"]),
}


class CaseSelectionError(ValueError):
    """A generated case cannot be safely selected or executed."""


class CompiledCaseRepository:
    """Find compiled case data; it does not execute processes."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def all(self) -> list[dict[str, Any]]:
        LOGGER.info("event=compatibility.case_repository.read.before path=%s", self._path)
        document = json.loads(self._path.read_text(encoding="utf-8"))
        cases = document.get("cases")
        if not isinstance(cases, list):
            raise CaseSelectionError(
                "generated evidence has no case list; "
                "fix_hint=run-make-compatibility-evidence-generate"
            )
        LOGGER.info("event=compatibility.case_repository.read.after cases=%d", len(cases))
        return cases

    def get(self, case_id: str) -> dict[str, Any]:
        matches = [case for case in self.all() if case.get("id") == case_id]
        if len(matches) != 1:
            message = (
                f"case selection must resolve exactly once case_id={case_id!r} "
                f"matches={len(matches)}"
            )
            raise CaseSelectionError(message)
        return matches[0]


class TimeoutConfiguration:
    """Read the case timeout from repository configuration, never from hard-coded runner values."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def seconds(self, dotted_path: str) -> int:
        value: Any = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        for part in dotted_path.split("."):
            if not isinstance(value, dict) or part not in value:
                raise CaseSelectionError(
                    f"missing timeout configuration path={dotted_path} config={self._path}"
                )
            value = value[part]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise CaseSelectionError(f"timeout must be a positive integer path={dotted_path}")
        return value


class IsolatedCaseRunner:
    """Translate one compiled runner adapter into a bounded child process."""

    def __init__(self, *, root: Path, timeout_configuration: TimeoutConfiguration) -> None:
        self._root = root
        self._timeouts = timeout_configuration

    def command(
        self, case: dict[str, Any], *, junitxml: Path | None = None
    ) -> tuple[list[str], int]:
        runner = case["runner"]
        scenario = case["scenario"]
        kind = runner.get("kind")
        approved = APPROVED_RUNNERS.get(kind)
        if approved is None:
            raise CaseSelectionError(f"unknown generated runner kind={kind!r}")
        marker, prefix = approved
        if runner.get("command_prefix") != prefix or scenario.get("kind") != marker:
            raise CaseSelectionError(
                f"generated runner contract mismatch case_id={case.get('id')} "
                "fix_hint=regenerate-and-review-evidence"
            )
        nodes = scenario.get("test_nodes")
        if not isinstance(nodes, list) or not nodes:
            raise CaseSelectionError(f"case has no test nodes case_id={case.get('id')}")
        timeout = self._timeouts.seconds(runner["timeout_config_path"])
        command = [
            *prefix,
            *nodes,
            "-m",
            marker,
            "--timeout",
            str(timeout),
            "--timeout-method",
            "thread",
            "-vv",
        ]
        if junitxml is not None:
            command.extend(("--junitxml", str(junitxml)))
        return command, timeout

    def run(
        self,
        case: dict[str, Any],
        *,
        dry_run: bool = False,
        junitxml: Path | None = None,
    ) -> int:
        command, timeout = self.command(case, junitxml=junitxml)
        profiles = case.get("compatibility_profiles", {})
        versions = {
            name: value
            for profile in profiles.values()
            for name, value in profile.get("versions", {}).items()
        }
        fingerprints = {
            service: value
            for profile in profiles.values()
            for service, value in profile.get("model_fingerprints", {}).items()
        }
        LOGGER.info(
            "event=compatibility.case.run.before case_id=%s evidence_sha256=%s lane=%s "
            "versions=%s model_fingerprints=%s scenario_ids=%s timeout_seconds=%d junitxml=%s "
            "dry_run=%s",
            case["id"],
            case["evidence_sha256"],
            case["lane"],
            json.dumps(versions, sort_keys=True, separators=(",", ":")),
            json.dumps(fingerprints, sort_keys=True, separators=(",", ":")),
            json.dumps(case["scenario"]["scenario_ids"], separators=(",", ":")),
            timeout,
            junitxml,
            str(dry_run).lower(),
        )
        if dry_run:
            print(json.dumps({"case_id": case["id"], "command": command, "timeout": timeout}))
            return 0
        if junitxml is not None:
            output_path = junitxml if junitxml.is_absolute() else self._root / junitxml
            output_path.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["MYSTACK_COMPATIBILITY_CASE_ID"] = case["id"]
        environment["MYSTACK_COMPATIBILITY_EVIDENCE_SHA256"] = case["evidence_sha256"]
        try:
            completed = subprocess.run(
                command,
                cwd=self._root,
                env=environment,
                check=False,
                timeout=timeout + 30,
            )
        except subprocess.TimeoutExpired as error:
            LOGGER.error(
                "event=compatibility.case.run.timeout case_id=%s timeout_seconds=%d "
                "fix_hint=inspect-test-timeout-and-component-thread-diagnostics",
                case["id"],
                timeout,
            )
            raise CaseSelectionError(f"case process timed out case_id={case['id']}") from error
        level = logging.INFO if completed.returncode == 0 else logging.ERROR
        LOGGER.log(
            level,
            "event=compatibility.case.run.after case_id=%s returncode=%d fix_hint=%s",
            case["id"],
            completed.returncode,
            "none" if completed.returncode == 0 else "search-logs-by-case-id-and-evidence-sha256",
        )
        return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", nargs="?")
    parser.add_argument("--matrix", type=Path, default=EVIDENCE_JSON)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("MYSTACK_CONFIG_FILE", ROOT / "config/runtime/mystack.yaml")),
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--junitxml",
        type=Path,
        help="Write the selected pytest case result as JUnit XML for CI evidence.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = parse_args()
    repository = CompiledCaseRepository(args.matrix)
    try:
        if args.list:
            print("\n".join(case["id"] for case in repository.all()))
            return
        if not args.case_id:
            raise CaseSelectionError("case_id is required unless --list is used")
        case = repository.get(args.case_id)
        runner = IsolatedCaseRunner(
            root=ROOT,
            timeout_configuration=TimeoutConfiguration(args.config),
        )
        raise SystemExit(runner.run(case, dry_run=args.dry_run, junitxml=args.junitxml))
    except CaseSelectionError as error:
        LOGGER.error("event=compatibility.case.failed error=%s", error)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
