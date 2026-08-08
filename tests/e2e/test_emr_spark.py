"""Public-proxy E2E for boto3 -> EMR -> bootstrap -> Spark -> LocalStack S3.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-commandrunner.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html
"""

from __future__ import annotations

import json
import subprocess
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
    jar_artifact = _copy_jar_fixture(e2e_settings)
    s3.upload_file(str(jar_artifact), bucket, "inputs/spark-s3-job.jar")

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
    assert marker == (b"runtime_user=hadoop\nsudo_user=root\nvenv=/home/hadoop/mystack-e2e-venv\n")
    assert emr.list_clusters(ClusterStates=["WAITING"])["Clusters"][0]["Id"] == cluster_id
    assert emr.list_bootstrap_actions(ClusterId=cluster_id)["BootstrapActions"][0]["Name"] == (
        "write-s3-marker"
    )

    emr.add_tags(ResourceId=cluster_id, Tags=[{"Key": "owner", "Value": "mystack-e2e"}])
    assert {
        tag["Key"] for tag in emr.describe_cluster(ClusterId=cluster_id)["Cluster"]["Tags"]
    } == {"owner"}
    emr.remove_tags(ResourceId=cluster_id, TagKeys=["owner"])
    emr.set_visible_to_all_users(JobFlowIds=[cluster_id], VisibleToAllUsers=False)
    assert emr.describe_cluster(ClusterId=cluster_id)["Cluster"]["VisibleToAllUsers"] is False

    step_ids = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "real-spark-s3a-write",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Properties": [
                        {
                            "Key": "spark.pyspark.python",
                            "Value": "/home/hadoop/mystack-e2e-venv/bin/python",
                        },
                        {
                            "Key": "spark.pyspark.driver.python",
                            "Value": "/home/hadoop/mystack-e2e-venv/bin/python",
                        },
                    ],
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/inputs/spark_s3_job.py",
                        "--output",
                        f"s3a://{bucket}/results/spark-json",
                        "--row-count",
                        "7",
                    ],
                },
            },
            {
                "Name": "real-spark-jar-s3a-write",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "MainClass": "mystack.e2e.SparkS3JarJob",
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/inputs/spark-s3-job.jar",
                        "--output",
                        f"s3a://{bucket}/results/spark-jar-json",
                        "--row-count",
                        "5",
                    ],
                },
            },
        ],
    )["StepIds"]
    for step_id in step_ids:
        step = _wait_for_step(emr, cluster_id, step_id, {"COMPLETED", "FAILED"}, e2e_settings)
        assert step["Status"]["State"] == "COMPLETED", step["Status"]

    listed_ids = {
        step["Id"] for step in emr.list_steps(ClusterId=cluster_id, StepIds=step_ids)["Steps"]
    }
    assert listed_ids == set(step_ids)

    objects = s3.list_objects_v2(Bucket=bucket, Prefix="results/spark-json/")
    keys = {value["Key"] for value in objects.get("Contents", ())}
    assert "results/spark-json/_SUCCESS" in keys
    data_key = next(key for key in keys if key.endswith(".json"))
    first_row = json.loads(
        s3.get_object(Bucket=bucket, Key=data_key)["Body"].read().splitlines()[0]
    )
    assert first_row["spark_version"].startswith(e2e_settings.emr_expected_spark_version_prefix)
    assert first_row["runtime_user"] == "hadoop"
    assert first_row["python_executable"] == "/home/hadoop/mystack-e2e-venv/bin/python"
    assert first_row["bootstrap_dependency"] == "installed-by-bootstrap"

    jar_row = _first_s3_json_row(s3, bucket, "results/spark-jar-json/")
    assert jar_row["spark_version"].startswith(e2e_settings.emr_expected_spark_version_prefix)

    cancel_step_id = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "cancel-running-spark",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Properties": [
                        {
                            "Key": "spark.pyspark.python",
                            "Value": "/home/hadoop/mystack-e2e-venv/bin/python",
                        },
                        {
                            "Key": "spark.pyspark.driver.python",
                            "Value": "/home/hadoop/mystack-e2e-venv/bin/python",
                        },
                    ],
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/inputs/spark_s3_job.py",
                        "--output",
                        f"s3a://{bucket}/results/should-not-complete",
                        "--row-count",
                        "1",
                        "--sleep-seconds",
                        "300",
                    ],
                },
            }
        ],
    )["StepIds"][0]
    _wait_for_step(emr, cluster_id, cancel_step_id, {"RUNNING"}, e2e_settings)
    cancelled = emr.cancel_steps(ClusterId=cluster_id, StepIds=[cancel_step_id])
    assert cancelled["CancelStepsInfoList"] == [{"StepId": cancel_step_id, "Status": "SUBMITTED"}]
    _wait_for_step(emr, cluster_id, cancel_step_id, {"CANCELLED"}, e2e_settings)

    emr.set_termination_protection(JobFlowIds=[cluster_id], TerminationProtected=True)
    emr.terminate_job_flows(JobFlowIds=[cluster_id])
    _wait_for_cluster(emr, cluster_id, {"WAITING"}, e2e_settings)
    emr.set_termination_protection(JobFlowIds=[cluster_id], TerminationProtected=False)
    emr.terminate_job_flows(JobFlowIds=[cluster_id])
    _wait_for_cluster(emr, cluster_id, {"TERMINATED"}, e2e_settings)


def _copy_jar_fixture(settings: Any) -> Path:
    destination = settings.artifacts_dir / "spark-s3-job.jar"
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "--file",
            str(settings.compose_file),
            "cp",
            f"{settings.emr_service}:{settings.emr_jar_fixture_container_path}",
            str(destination),
        ],
        cwd=settings.compose_file.parent,
        capture_output=True,
        text=True,
        timeout=settings.timeout_seconds,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return destination


def _first_s3_json_row(client: Any, bucket: str, prefix: str) -> dict[str, Any]:
    objects = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    keys = {value["Key"] for value in objects.get("Contents", ())}
    assert f"{prefix}_SUCCESS" in keys
    data_key = next(key for key in keys if key.endswith(".json"))
    return json.loads(client.get_object(Bucket=bucket, Key=data_key)["Body"].read().splitlines()[0])


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
