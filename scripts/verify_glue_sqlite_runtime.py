"""Run and retain one bounded Glue-image SQLite runtime capability report.

The release preflight invokes this script once per configured OCI platform after building its local
image. It never pulls a registry image or mutates a registry.

References:
- https://docs.docker.com/reference/cli/docker/container/run/
- https://www.sqlite.org/wal.html#the_wal_reset_bug
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class SQLiteRuntimePreflightError(RuntimeError):
    """The built Glue image did not report the expected verified WAL runtime."""


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
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime command did not complete within its configured timeout."
        ) from error
    if completed.returncode != 0:
        raise SQLiteRuntimePreflightError(
            "Glue image SQLite runtime command failed; inspect the container preflight logs."
        )
    runtime = _runtime_document(completed.stdout)
    _validate_runtime(runtime, expected_version, platform)
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
    parser.add_argument("--source-config", type=Path, default=Path("config/sqlite-runtime.json"))
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_version = load_expected_version(args.source_config)
    report = verify(
        image=args.image,
        platform=args.platform,
        timeout_seconds=args.timeout_seconds,
        expected_version=expected_version,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
