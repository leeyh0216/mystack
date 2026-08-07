"""Public-proxy E2E for boto3 -> EMR -> bootstrap -> Spark -> LocalStack S3.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-commandrunner.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.e2e
def test_boto3_runs_bootstrap_and_real_spark_through_public_proxy(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    emr = aws_clients["emr"]
    s3 = aws_clients["s3"]
    bucket = f"mystack-e2e-{uuid.uuid4().hex}"
    assets = Path(__file__).parent / "assets"
    s3.create_bucket(Bucket=bucket)
    s3.upload_file(str(assets / "bootstrap.sh"), bucket, "inputs/bootstrap.sh")
    s3.upload_file(str(assets / "spark_s3_job.py"), bucket, "inputs/spark_s3_job.py")

    created = emr.run_job_flow(
        Name="mystack-real-spark-e2e",
        ReleaseLabel=e2e_settings.emr_release_label,
        Instances={
            "MasterInstanceType": "m5.xlarge",
            "SlaveInstanceType": "m5.xlarge",
            "InstanceCount": 1,
            "KeepJobFlowAliveWhenNoSteps": True,
        },
        Applications=[{"Name": "Spark"}],
        BootstrapActions=[
            {
                "Name": "write-s3-marker",
                "ScriptBootstrapAction": {
                    "Path": f"s3://{bucket}/inputs/bootstrap.sh",
                    "Args": [bucket],
                },
            }
        ],
    )
    cluster_id = created["JobFlowId"]
    _wait_for_cluster(emr, cluster_id, {"WAITING"}, e2e_settings)
    marker = s3.get_object(Bucket=bucket, Key="results/bootstrap-marker.txt")["Body"].read()
    assert marker == b"bootstrap-completed\n"

    step_id = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "real-spark-s3a-write",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/inputs/spark_s3_job.py",
                        "--output",
                        f"s3a://{bucket}/results/spark-json",
                        "--row-count",
                        "7",
                    ],
                },
            }
        ],
    )["StepIds"][0]
    step = _wait_for_step(emr, cluster_id, step_id, {"COMPLETED", "FAILED"}, e2e_settings)
    assert step["Status"]["State"] == "COMPLETED", step["Status"]

    objects = s3.list_objects_v2(Bucket=bucket, Prefix="results/spark-json/")
    keys = {value["Key"] for value in objects.get("Contents", ())}
    assert "results/spark-json/_SUCCESS" in keys
    data_key = next(key for key in keys if key.endswith(".json"))
    first_row = json.loads(
        s3.get_object(Bucket=bucket, Key=data_key)["Body"].read().splitlines()[0]
    )
    assert first_row["spark_version"].startswith(e2e_settings.emr_expected_spark_version_prefix)

    emr.terminate_job_flows(JobFlowIds=[cluster_id])
    _wait_for_cluster(emr, cluster_id, {"TERMINATED"}, e2e_settings)


def _wait_for_cluster(
    client: Any,
    cluster_id: str,
    states: set[str],
    settings: Any,
) -> dict[str, Any]:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        cluster = client.describe_cluster(ClusterId=cluster_id)["Cluster"]
        if cluster["Status"]["State"] in states:
            return cluster
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Cluster {cluster_id} did not enter {sorted(states)}")


def _wait_for_step(
    client: Any,
    cluster_id: str,
    step_id: str,
    states: set[str],
    settings: Any,
) -> dict[str, Any]:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        step = client.describe_step(ClusterId=cluster_id, StepId=step_id)["Step"]
        if step["Status"]["State"] in states:
            return step
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Step {step_id} did not enter {sorted(states)}")
