"""Release-preflight contracts for the per-architecture Glue SQLite probe.

Reference: https://docs.docker.com/reference/cli/docker/container/run/
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.quality.verify_glue_sqlite_runtime import (
    SQLiteRuntimePreflightError,
    failure_report,
    load_expected_version,
    main,
    verify,
)

_PINNED_SQLITE_VERSION = load_expected_version(
    Path(__file__).parents[1] / "config/runtime/sqlite-runtime.json"
)


def _runtime(
    *,
    architecture: str = "x86_64",
    version: str = _PINNED_SQLITE_VERSION,
    manifest_verified: bool = True,
) -> dict[str, object]:
    return {
        "architecture": architecture,
        "auto_checkpoint_pages": 1000,
        "busy_timeout_milliseconds": 5000,
        "checkpoint_mode": "passive",
        "driver_module": "pysqlite3.dbapi2",
        "foreign_keys_enabled": True,
        "journal_mode": "wal",
        "manifest_verified": manifest_verified,
        "sqlite_version": version,
        "synchronous": "normal",
    }


def test_preflight_runs_the_bounded_image_cli_and_records_verified_runtime() -> None:
    captured: dict[str, object] = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, json.dumps(_runtime()), "")

    report = verify(
        image="mystack-preflight-glue:linux-amd64-sha",
        platform="linux/amd64",
        timeout_seconds=45,
        expected_version=_PINNED_SQLITE_VERSION,
        runner=runner,
    )

    assert captured["command"] == [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--entrypoint",
        "/opt/mystack/venv/bin/mystack-glue",
        "mystack-preflight-glue:linux-amd64-sha",
        "--config",
        "/etc/mystack/mystack.yaml",
        "--verify-sqlite-runtime",
    ]
    assert captured["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": 45,
    }
    assert report["runtime"] == _runtime()


def test_preflight_rejects_wrong_architecture_unverified_wal_or_wrong_version() -> None:
    def wrong_architecture(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            command, 0, json.dumps(_runtime(architecture="aarch64")), ""
        )

    with pytest.raises(SQLiteRuntimePreflightError, match="architecture"):
        verify(
            image="mystack-preflight-glue:wrong",
            platform="linux/amd64",
            timeout_seconds=1,
            expected_version=_PINNED_SQLITE_VERSION,
            runner=wrong_architecture,
        )

    def unverified_wal(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            command, 0, json.dumps(_runtime(manifest_verified=False)), ""
        )

    with pytest.raises(SQLiteRuntimePreflightError, match="source-built WAL path"):
        verify(
            image="mystack-preflight-glue:unverified",
            platform="linux/amd64",
            timeout_seconds=1,
            expected_version=_PINNED_SQLITE_VERSION,
            runner=unverified_wal,
        )

    def wrong_version(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(command, 0, json.dumps(_runtime(version="3.51.3")), "")

    with pytest.raises(SQLiteRuntimePreflightError, match="source-pinned SQLite version"):
        verify(
            image="mystack-preflight-glue:wrong-version",
            platform="linux/amd64",
            timeout_seconds=1,
            expected_version=_PINNED_SQLITE_VERSION,
            runner=wrong_version,
        )


def test_preflight_retains_a_bounded_redacted_diagnostic_on_container_failure() -> None:
    secret = "do-not-retain-this-secret"
    session_token = "FwoGZXIvYXdzEJr//////////wEaDO-realistic-session-token"
    security_token = "AQoDYXdzEJr-realistic-security-token"

    def failed_runtime(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            command,
            17,
            "x" * 5_000 + f"\nAWS_SECRET_ACCESS_KEY={secret}\nlast-stdout-line",
            "\n".join(
                (
                    f"Authorization: Bearer {secret}",
                    f"https://user:{secret}@example.test/path?token={secret}",
                    f"AWS_SESSION_TOKEN={session_token}",
                    f"AWS_SECURITY_TOKEN={security_token}",
                )
            ),
        )

    with pytest.raises(SQLiteRuntimePreflightError, match="retained preflight report") as error:
        verify(
            image="ghcr.io/example/mystack-glue@sha256:" + "a" * 64,
            platform="linux/amd64",
            timeout_seconds=45,
            expected_version=_PINNED_SQLITE_VERSION,
            runner=failed_runtime,
        )

    diagnostic = error.value.diagnostic
    assert diagnostic is not None
    serialized = json.dumps(diagnostic)
    assert secret not in serialized
    assert session_token not in serialized
    assert security_token not in serialized
    assert diagnostic["status"] == "failed"
    failure = diagnostic["failure"]
    assert failure == {
        "kind": "nonzero_exit",
        "returncode": 17,
        "stdout_tail": failure["stdout_tail"],
        "stderr_tail": failure["stderr_tail"],
    }
    assert "[truncated to final 4096 characters]" in failure["stdout_tail"]
    assert "[REDACTED]" in failure["stdout_tail"]
    assert "[REDACTED]" in failure["stderr_tail"]


def test_cli_writes_a_failure_artifact_when_the_runtime_probe_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "sqlite-runtime.json"
    diagnostic = failure_report(
        image="mystack-preflight-glue:failed",
        platform="linux/amd64",
        timeout_seconds=45,
        kind="nonzero_exit",
        returncode=1,
        stderr="token=do-not-retain",
    )

    def failed_verify(**kwargs):
        del kwargs
        raise SQLiteRuntimePreflightError("failed", diagnostic=diagnostic)

    monkeypatch.setattr("scripts.quality.verify_glue_sqlite_runtime.verify", failed_verify)

    assert (
        main(
            [
                "--image",
                "mystack-preflight-glue:failed",
                "--platform",
                "linux/amd64",
                "--timeout-seconds",
                "45",
                "--source-config",
                "config/runtime/sqlite-runtime.json",
                "--report",
                str(report_path),
            ]
        )
        == 2
    )
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == diagnostic
    assert "do-not-retain" not in report_path.read_text(encoding="utf-8")
