"""Release-preflight contracts for the per-architecture Glue SQLite probe.

Reference: https://docs.docker.com/reference/cli/docker/container/run/
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.verify_glue_sqlite_runtime import (
    SQLiteRuntimePreflightError,
    load_expected_version,
    verify,
)

_PINNED_SQLITE_VERSION = load_expected_version(
    Path(__file__).parents[1] / "config/sqlite-runtime.json"
)


def _runtime(
    *,
    architecture: str = "x86_64",
    version: str = _PINNED_SQLITE_VERSION,
) -> dict[str, object]:
    return {
        "architecture": architecture,
        "auto_checkpoint_pages": 1000,
        "busy_timeout_milliseconds": 5000,
        "checkpoint_mode": "passive",
        "driver_module": "pysqlite3.dbapi2",
        "foreign_keys_enabled": True,
        "journal_mode": "wal",
        "manifest_verified": True,
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


def test_preflight_rejects_a_wrong_runtime_architecture_or_unverified_wal() -> None:
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
