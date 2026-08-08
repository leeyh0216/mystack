"""Failure-injection proof for EMR Step journal and S3 publication recovery.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
- https://docs.docker.com/reference/cli/docker/compose/restart/
"""

from __future__ import annotations

import gzip
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from botocore.exceptions import ClientError


@pytest.mark.e2e
def test_running_step_logs_and_publication_recover_after_emr_restart(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    emr = aws_clients["emr"]
    s3 = aws_clients["s3"]
    bucket = f"mystack-recovery-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)
    s3.upload_file(
        str(Path(__file__).parent / "assets" / "console_long_step.py"),
        bucket,
        "jobs/recovery.py",
    )
    cluster_id = emr.run_job_flow(
        Name="restart-recovery-e2e",
        ReleaseLabel=e2e_settings.emr_release_label,
        LogUri=f"s3://{bucket}/logs/",
        Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
        Applications=[{"Name": "Spark"}],
    )["JobFlowId"]
    _wait_for_cluster(emr, cluster_id, {"WAITING"}, e2e_settings)
    step_id = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "restart-recovery-step",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/jobs/recovery.py",
                        "--sleep-seconds",
                        "120",
                    ],
                },
            }
        ],
    )["StepIds"][0]
    _wait_for_step(emr, cluster_id, step_id, {"RUNNING"}, e2e_settings)
    _wait_for_live_output(cluster_id, step_id, e2e_settings)

    restarted = subprocess.run(
        [
            "docker",
            "compose",
            "--file",
            str(e2e_settings.compose_file),
            "restart",
            e2e_settings.emr_service,
        ],
        cwd=e2e_settings.compose_file.parent,
        capture_output=True,
        text=True,
        timeout=e2e_settings.timeout_seconds,
        check=False,
    )
    assert restarted.returncode == 0, restarted.stderr

    recovered = _wait_for_recovered_projection(cluster_id, step_id, e2e_settings)
    assert recovered["step_state"] == "INTERRUPTED"
    assert recovered["recovered"] is True
    assert "console-long-step-started" in recovered["stdout"]
    assert recovered["log_publication"]["status"] == "published"

    with pytest.raises(ClientError) as not_found:
        emr.describe_cluster(ClusterId=cluster_id)
    assert not_found.value.response["Error"]["Code"] == "InvalidRequestException"

    key = f"logs/{cluster_id}/steps/{step_id}/stdout.gz"
    archived = gzip.decompress(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    assert b"console-long-step-started" in archived


def _wait_for_live_output(cluster_id: str, step_id: str, settings: Any) -> None:
    deadline = time.monotonic() + settings.timeout_seconds
    with _http_client(settings) as client:
        while time.monotonic() < deadline:
            response = client.get(
                "/_mystack/components/emr/logs",
                params={"cluster_id": cluster_id, "step_id": step_id},
            )
            if response.status_code == 200:
                stdout = response.json()["stdout"]
                if "console-long-step-started" in stdout:
                    return
            time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Step {step_id} did not emit live output")


def _wait_for_recovered_projection(
    cluster_id: str,
    step_id: str,
    settings: Any,
) -> dict[str, Any]:
    deadline = time.monotonic() + settings.timeout_seconds
    with _http_client(settings) as client:
        while time.monotonic() < deadline:
            try:
                resources = client.get("/_mystack/components/emr/resources")
                logs = client.get(
                    "/_mystack/components/emr/logs",
                    params={"cluster_id": cluster_id, "step_id": step_id},
                )
            except httpx.HTTPError:
                time.sleep(settings.poll_interval_seconds)
                continue
            if resources.status_code == 200 and logs.status_code == 200:
                clusters = resources.json()["resources"]["clusters"]
                recovered = any(
                    value["id"] == cluster_id and value["recovered"] for value in clusters
                )
                document = logs.json()
                if recovered and document["log_publication"]["status"] == "published":
                    return document
            time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Step {step_id} did not recover after EMR restart")


def _http_client(settings: Any) -> httpx.Client:
    return httpx.Client(
        base_url=settings.endpoint_url,
        timeout=httpx.Timeout(
            settings.sdk_read_timeout_seconds,
            connect=settings.sdk_connect_timeout_seconds,
        ),
    )


def _wait_for_cluster(client: Any, cluster_id: str, states: set[str], settings: Any) -> None:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        cluster = client.describe_cluster(ClusterId=cluster_id)["Cluster"]
        if cluster["Status"]["State"] in states:
            return
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Cluster {cluster_id} did not enter {sorted(states)}")


def _wait_for_step(
    client: Any,
    cluster_id: str,
    step_id: str,
    states: set[str],
    settings: Any,
) -> None:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        step = client.describe_step(ClusterId=cluster_id, StepId=step_id)["Step"]
        if step["Status"]["State"] in states:
            return
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Step {step_id} did not enter {sorted(states)}")
