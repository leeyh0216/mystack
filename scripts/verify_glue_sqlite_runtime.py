"""Run and retain one bounded Glue-image SQLite runtime capability report.

The local release preflight invokes this reusable verifier once per configured OCI platform after
building a local image. Post-push anonymous verification invokes the same verifier against an exact
published platform digest, which Docker may pull. The verifier never mutates a registry.

References:
- https://docs.docker.com/reference/cli/docker/container/run/
- https://www.sqlite.org/wal.html#the_wal_reset_bug
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_DIAGNOSTIC_TAIL_LIMIT = 4_096
_URI_CREDENTIAL_PATTERN = re.compile(r"(?P<prefix>[a-z][a-z0-9+.-]*://)[^\s/@]+@", re.IGNORECASE)
_QUERY_VALUE_PATTERN = re.compile(r"(?P<prefix>[?&][^=\s&#]+)=([^\s&#]*)")
_AUTHORIZATION_VALUE_PATTERN = re.compile(
    r"(?P<prefix>\bauthorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:aws[_-])?(?:access[_-]?key(?:[_-]?id)?|authorization|"
    r"credential(?:s)?|password|secret(?:[_-][a-z]+)*|(?:session|security)[_-]?token|token)"
    r"\s*(?:=|:)\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
_AWS_ACCESS_KEY_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


class SQLiteRuntimePreflightError(RuntimeError):
    """The built Glue image did not report the expected verified WAL runtime."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


def emit(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True), file=sys.stderr, flush=True)


def load_expected_version(path: Path) -> str:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        version = document["sqlite"]["version"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SQLiteRuntimePreflightError(
            "SQLite runtime preflight cannot read the source-pinned expected version."
        ) from error
    if not isinstance(version, str) or not version:
        raise SQLiteRuntimePreflightError("SQLite runtime preflight expected version is invalid.")
    return version


def redacted_tail(value: str | bytes | None, *, limit: int = _DIAGNOSTIC_TAIL_LIMIT) -> str:
    """Keep a bounded diagnostic tail while removing common credential-bearing forms."""
    if limit <= 0:
        raise ValueError("diagnostic tail limit must be positive")
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    redacted = _URI_CREDENTIAL_PATTERN.sub(r"\g<prefix>[REDACTED]@", value)
    redacted = _QUERY_VALUE_PATTERN.sub(r"\g<prefix>=[REDACTED]", redacted)
    redacted = _AUTHORIZATION_VALUE_PATTERN.sub(r"\g<prefix>[REDACTED]", redacted)
    redacted = _SENSITIVE_ASSIGNMENT_PATTERN.sub(r"\g<prefix>[REDACTED]", redacted)
    redacted = _AWS_ACCESS_KEY_PATTERN.sub("[REDACTED_AWS_ACCESS_KEY]", redacted)
    if len(redacted) <= limit:
        return redacted
    return f"[truncated to final {limit} characters]\n{redacted[-limit:]}"


def failure_report(
    *,
    image: str,
    platform: str,
    timeout_seconds: float,
    kind: str,
    returncode: int | None = None,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
) -> dict[str, object]:
    """Create an artifact-safe failure document without retaining unbounded container output."""
    return {
        "schema_version": 1,
        "status": "failed",
        "image": image,
        "platform": platform,
        "timeout_seconds": timeout_seconds,
        "failure": {
            "kind": kind,
            "returncode": returncode,
            "stdout_tail": redacted_tail(stdout),
            "stderr_tail": redacted_tail(stderr),
        },
    }


def _raise_failure(
    message: str,
    *,
    image: str,
    platform: str,
    timeout_seconds: float,
    kind: str,
    returncode: int | None = None,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
) -> None:
    diagnostic = failure_report(
        image=image,
        platform=platform,
        timeout_seconds=timeout_seconds,
        kind=kind,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    emit(
        "glue.sqlite.preflight.failed",
        image=image,
        platform=platform,
        failure=diagnostic["failure"],
    )
    raise SQLiteRuntimePreflightError(message, diagnostic=diagnostic)


def verify(
    *,
    image: str,
    platform: str,
    timeout_seconds: float,
    expected_version: str,
    runner: Any = subprocess.run,
) -> dict[str, object]:
    if timeout_seconds <= 0:
        raise SQLiteRuntimePreflightError("SQLite runtime preflight timeout must be positive.")
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        platform,
        "--entrypoint",
        "/opt/mystack/venv/bin/mystack-glue",
        image,
        "--config",
        "/etc/mystack/mystack.yaml",
        "--verify-sqlite-runtime",
    ]
    emit(
        "glue.sqlite.preflight.before",
        image=image,
        platform=platform,
        timeout_seconds=timeout_seconds,
    )
    try:
        completed = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        _raise_failure(
            "Glue image SQLite runtime command did not complete within its configured timeout.",
            image=image,
            platform=platform,
            timeout_seconds=timeout_seconds,
            kind="timeout",
            stdout=error.stdout,
            stderr=error.stderr,
        )
    except OSError as error:
        _raise_failure(
            "Glue image SQLite runtime command could not be started; inspect the preflight report.",
            image=image,
            platform=platform,
            timeout_seconds=timeout_seconds,
            kind=type(error).__name__,
        )
    if completed.returncode != 0:
        _raise_failure(
            "Glue image SQLite runtime command failed; inspect the retained preflight report.",
            image=image,
            platform=platform,
            timeout_seconds=timeout_seconds,
            kind="nonzero_exit",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    try:
        runtime = _runtime_document(completed.stdout)
        _validate_runtime(runtime, expected_version, platform)
    except SQLiteRuntimePreflightError as error:
        _raise_failure(
            str(error),
            image=image,
            platform=platform,
            timeout_seconds=timeout_seconds,
            kind="invalid_runtime_report",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    report = {
        "schema_version": 1,
        "image": image,
        "platform": platform,
        "timeout_seconds": timeout_seconds,
        "runtime": runtime,
    }
    emit(
        "glue.sqlite.preflight.after",
        image=image,
        platform=platform,
        sqlite_version=runtime["sqlite_version"],
        architecture=runtime["architecture"],
    )
    return report


def _runtime_document(stdout: str) -> dict[str, object]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime command produced no JSON report."
        )
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime report is not valid JSON."
        ) from error
    if not isinstance(value, dict):
        raise SQLiteRuntimePreflightError("Glue image SQLite runtime report must be a JSON object.")
    return value


def _validate_runtime(
    runtime: dict[str, object],
    expected_version: str,
    platform: str,
) -> None:
    required = {
        "architecture",
        "auto_checkpoint_pages",
        "busy_timeout_milliseconds",
        "checkpoint_mode",
        "driver_module",
        "foreign_keys_enabled",
        "journal_mode",
        "manifest_verified",
        "sqlite_version",
        "synchronous",
    }
    if set(runtime) != required:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime report has an unexpected shape."
        )
    if runtime["sqlite_version"] != expected_version:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime does not match the source-pinned SQLite version."
        )
    if runtime["journal_mode"] != "wal" or runtime["manifest_verified"] is not True:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime did not prove the configured source-built WAL path."
        )
    if runtime["foreign_keys_enabled"] is not True:
        raise SQLiteRuntimePreflightError("Glue image SQLite runtime did not enable foreign keys.")
    if not isinstance(runtime["architecture"], str) or not runtime["architecture"]:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime did not report its architecture."
        )
    expected_architectures = {
        "linux/amd64": {"amd64", "x86_64"},
        "linux/arm64": {"aarch64", "arm64"},
    }
    if runtime["architecture"] not in expected_architectures.get(platform, set()):
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime architecture does not match the requested OCI platform."
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument(
        "--source-config", type=Path, default=Path("config/runtime/sqlite-runtime.json")
    )
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        expected_version = load_expected_version(args.source_config)
        report = verify(
            image=args.image,
            platform=args.platform,
            timeout_seconds=args.timeout_seconds,
            expected_version=expected_version,
        )
    except SQLiteRuntimePreflightError as error:
        report = error.diagnostic or failure_report(
            image=args.image,
            platform=args.platform,
            timeout_seconds=args.timeout_seconds,
            kind="configuration",
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        emit(
            "glue.sqlite.preflight.report_written",
            status="failed",
            report=str(args.report),
        )
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    emit("glue.sqlite.preflight.report_written", status="verified", report=str(args.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
