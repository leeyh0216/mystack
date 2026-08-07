"""Black-box boto3 contracts for every currently implemented EMR operation.

API reference: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
"""

from __future__ import annotations

import time

import pytest
from botocore.exceptions import ClientError


@pytest.mark.contract
def test_boto3_cluster_step_and_control_operations(
    emr_client,
    emr_server,
    test_timeout: float,
) -> None:
    _, runtime = emr_server
    created = emr_client.run_job_flow(
        Name="contract-cluster",
        ReleaseLabel="emr-7.8.0",
        Instances={
            "MasterInstanceType": "m5.xlarge",
            "SlaveInstanceType": "m5.xlarge",
            "InstanceCount": 1,
            "KeepJobFlowAliveWhenNoSteps": True,
        },
        Applications=[{"Name": "Spark"}],
        BootstrapActions=[
            {
                "Name": "setup",
                "ScriptBootstrapAction": {"Path": "s3://assets/bootstrap.sh", "Args": ["x"]},
            }
        ],
        Tags=[{"Key": "environment", "Value": "test"}],
    )
    cluster_id = created["JobFlowId"]
    cluster = wait_for_cluster_state(emr_client, cluster_id, {"WAITING"}, test_timeout)
    assert created["ClusterArn"].endswith(f"cluster/{cluster_id}")
    assert cluster["ReleaseLabel"] == "emr-7.8.0"
    assert emr_client.list_clusters(ClusterStates=["WAITING"])["Clusters"][0]["Id"] == cluster_id
    assert (
        emr_client.list_bootstrap_actions(ClusterId=cluster_id)["BootstrapActions"][0]["Name"]
        == "setup"
    )

    added = emr_client.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "spark",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": ["spark-submit", "s3://assets/job.py"],
                },
            }
        ],
    )
    step_id = added["StepIds"][0]
    step = wait_for_step_state(emr_client, cluster_id, step_id, {"COMPLETED"}, test_timeout)
    assert step["Config"]["Jar"] == "command-runner.jar"
    assert (
        emr_client.list_steps(ClusterId=cluster_id, StepIds=[step_id])["Steps"][0]["Id"] == step_id
    )

    emr_client.add_tags(ResourceId=cluster_id, Tags=[{"Key": "owner", "Value": "mystack"}])
    assert {
        tag["Key"] for tag in emr_client.describe_cluster(ClusterId=cluster_id)["Cluster"]["Tags"]
    } == {
        "environment",
        "owner",
    }
    emr_client.remove_tags(ResourceId=cluster_id, TagKeys=["owner"])
    emr_client.set_visible_to_all_users(JobFlowIds=[cluster_id], VisibleToAllUsers=False)
    emr_client.set_termination_protection(JobFlowIds=[cluster_id], TerminationProtected=True)
    emr_client.terminate_job_flows(JobFlowIds=[cluster_id])
    assert (
        emr_client.describe_cluster(ClusterId=cluster_id)["Cluster"]["Status"]["State"] == "WAITING"
    )
    emr_client.set_termination_protection(JobFlowIds=[cluster_id], TerminationProtected=False)
    emr_client.terminate_job_flows(JobFlowIds=[cluster_id])
    wait_for_cluster_state(emr_client, cluster_id, {"TERMINATED"}, test_timeout)
    assert runtime.started.is_set()


@pytest.mark.contract
def test_boto3_cancel_steps(emr_client, emr_server, test_timeout: float) -> None:
    _, runtime = emr_server
    runtime.block_steps = True
    created = emr_client.run_job_flow(
        Name="cancel-cluster",
        Instances={
            "MasterInstanceType": "m5.xlarge",
            "SlaveInstanceType": "m5.xlarge",
            "InstanceCount": 1,
            "KeepJobFlowAliveWhenNoSteps": True,
        },
    )
    cluster_id = created["JobFlowId"]
    wait_for_cluster_state(emr_client, cluster_id, {"WAITING"}, test_timeout)
    step_id = emr_client.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "blocking",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": ["spark-submit", "job.py"],
                },
            }
        ],
    )["StepIds"][0]
    assert runtime.started.wait(test_timeout)
    response = emr_client.cancel_steps(ClusterId=cluster_id, StepIds=[step_id])
    assert response["CancelStepsInfoList"] == [{"StepId": step_id, "Status": "SUBMITTED"}]
    wait_for_step_state(emr_client, cluster_id, step_id, {"CANCELLED"}, test_timeout)


@pytest.mark.contract
def test_boto3_receives_documented_invalid_request(emr_client) -> None:
    with pytest.raises(ClientError) as captured:
        emr_client.describe_cluster(ClusterId="j-DOESNOTEXIST")
    response = captured.value.response
    assert response["Error"]["Code"] == "InvalidRequestException"
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 400


def wait_for_cluster_state(client, cluster_id: str, states: set[str], timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cluster = client.describe_cluster(ClusterId=cluster_id)["Cluster"]
        if cluster["Status"]["State"] in states:
            return cluster
        time.sleep(0.01)
    raise TimeoutError(f"Cluster {cluster_id} did not enter {sorted(states)}")


def wait_for_step_state(client, cluster_id: str, step_id: str, states: set[str], timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        step = client.describe_step(ClusterId=cluster_id, StepId=step_id)["Step"]
        if step["Status"]["State"] in states:
            return step
        time.sleep(0.01)
    raise TimeoutError(f"Step {step_id} did not enter {sorted(states)}")
