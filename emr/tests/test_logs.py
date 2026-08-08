"""EMR S3 Step/Application log publication contracts.

Official layouts:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mystack.emr.adapters.outbound.logs import S3StepLogPublisher, StepLogPublicationRequest


class _Objects:
    def __init__(
        self, *, failure: Exception | None = None, failures_before_success: int = 0
    ) -> None:
        self.values: dict[tuple[str, str], dict[str, Any]] = {}
        self.failure = failure
        self.failures_before_success = failures_before_success
        self.put_count = 0
        self.close_count = 0

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        self.put_count += 1
        if self.failure is not None or self.put_count <= self.failures_before_success:
            raise self.failure or RuntimeError("transient object store failure")
        self.values[(kwargs["Bucket"], kwargs["Key"])] = kwargs
        return {"ETag": "test"}

    def close(self) -> None:
        self.close_count += 1


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        endpoint_url="http://localstack:4566",
        region="us-east-1",
        access_key_id="test",
        secret_access_key="test",
        s3_path_style=True,
    )


def _policy(*, attempts: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        publication_max_attempts=attempts,
        publication_initial_backoff_seconds=0,
        publication_max_backoff_seconds=0,
        publication_attempt_timeout_seconds=1,
    )


def _request(
    tmp_path: Path,
    *,
    log_uri: str | None = "s3://logs/team/emr/",
) -> StepLogPublicationRequest:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_bytes(b"driver output\n")
    stderr.write_bytes(b"driver error\n")
    return StepLogPublicationRequest(
        cluster_id="j-ABC",
        step_id="s-123",
        log_uri=log_uri,
        work_dir=tmp_path,
        process_started=True,
        exit_code=0,
        reason="",
        stdout_file=stdout,
        stderr_file=stderr,
    )


@pytest.mark.asyncio
async def test_publishes_official_step_paths_and_synthetic_local_application_paths(
    tmp_path: Path,
) -> None:
    objects = _Objects()
    publisher = S3StepLogPublisher(_settings(), _policy(), client=objects)

    await publisher.publish(_request(tmp_path))
    await publisher.close()
    await publisher.close()

    keys = {key for bucket, key in objects.values if bucket == "logs"}
    step_prefix = "team/emr/j-ABC/steps/s-123"
    assert {
        f"{step_prefix}/controller.gz",
        f"{step_prefix}/syslog.gz",
        f"{step_prefix}/stdout.gz",
        f"{step_prefix}/stderr.gz",
    }.issubset(keys)
    application_keys = sorted(key for key in keys if "/containers/application_local_" in key)
    assert len(application_keys) == 2
    assert application_keys[0].endswith("/stderr.gz")
    assert application_keys[1].endswith("/stdout.gz")
    stdout = objects.values[("logs", f"{step_prefix}/stdout.gz")]
    assert stdout["ContentEncoding"] == "gzip"
    assert gzip.decompress(stdout["Body"]) == b"driver output\n"
    publication = json.loads((tmp_path / "log-publication.json").read_text())
    assert publication["status"] == "published"
    assert publication["runtime_mode"].startswith("Spark local/client mode")
    assert publication["exit_code"] == 0
    assert objects.close_count == 1


@pytest.mark.asyncio
async def test_missing_log_uri_skips_s3_mutation(tmp_path: Path) -> None:
    objects = _Objects()
    publisher = S3StepLogPublisher(_settings(), _policy(), client=objects)

    await publisher.publish(_request(tmp_path, log_uri=None))

    assert objects.values == {}
    publication = json.loads((tmp_path / "log-publication.json").read_text())
    assert publication == {
        "cluster_id": "j-ABC",
        "exit_code": 0,
        "process_started": True,
        "reason": "LogUri is not configured",
        "schema_version": 1,
        "status": "skipped",
        "step_id": "s-123",
    }


@pytest.mark.asyncio
async def test_upload_failure_is_recorded_without_replacing_process_result(tmp_path: Path) -> None:
    objects = _Objects(failure=RuntimeError("object store unavailable"))
    publisher = S3StepLogPublisher(_settings(), _policy(), client=objects)

    await publisher.publish(_request(tmp_path))

    publication = json.loads((tmp_path / "log-publication.json").read_text())
    assert publication["status"] == "failed"
    assert publication["exit_code"] == 0
    assert publication["process_started"] is True
    assert publication["error_type"] == "RuntimeError"
    assert publication["published_keys"] == []


@pytest.mark.asyncio
async def test_transient_upload_failure_retries_deterministic_keys(tmp_path: Path) -> None:
    objects = _Objects(failures_before_success=1)
    publisher = S3StepLogPublisher(_settings(), _policy(attempts=2), client=objects)

    await publisher.publish(_request(tmp_path))

    publication = json.loads((tmp_path / "log-publication.json").read_text())
    outbox = json.loads((tmp_path / "publication-request.json").read_text())
    assert publication["status"] == "published"
    assert publication["attempt"] == 2
    assert outbox["status"] == "published"
    assert outbox["attempt"] == 2
