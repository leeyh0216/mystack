"""Trusted EMR pre-start, environment propagation, inventory, and PID 1 contracts.

References:
- https://docs.docker.com/reference/dockerfile/#entrypoint
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
- https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

_MARKER = "trusted-root-environment-reached-hadoop"


@pytest.mark.e2e
def test_prestart_environment_reaches_service_bootstrap_and_spark(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    _require_prestart()
    assets = Path(__file__).parent / "assets"
    emr = aws_clients["emr"]
    s3 = aws_clients["s3"]
    bucket = f"mystack-prestart-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)
    s3.upload_file(str(assets / "prestart_bootstrap.sh"), bucket, "inputs/bootstrap.sh")
    s3.upload_file(str(assets / "prestart_spark_job.py"), bucket, "inputs/spark.py")

    process_contract = _compose(
        e2e_settings,
        [
            "exec",
            "-T",
            "--user",
            "root",
            e2e_settings.emr_service,
            "python3.11",
            "-c",
            "import os; assert os.stat('/proc/1').st_uid == 10001",
        ],
    )
    assert process_contract.returncode == 0, process_contract.stderr

    order = _compose(
        e2e_settings,
        [
            "exec",
            "-T",
            "--user",
            "hadoop",
            e2e_settings.emr_service,
            "python3.11",
            "-c",
            "print(open('/var/lib/mystack/emr/prestart-e2e-order.txt').read(), end='')",
        ],
    )
    assert order.returncode == 0, order.stderr
    order_lines = order.stdout.splitlines()
    assert order_lines
    assert len(order_lines) % 2 == 0
    assert all(
        pair == ("10-root-ca", "20-environment")
        for pair in zip(order_lines[::2], order_lines[1::2], strict=True)
    )

    live_inventory = _compose(
        e2e_settings,
        [
            "exec",
            "-T",
            "--user",
            "hadoop",
            e2e_settings.emr_service,
            "mystack-emr-runtime-inventory",
        ],
    )
    assert live_inventory.returncode == 0, live_inventory.stderr
    inventory = json.loads(live_inventory.stdout)
    assert inventory["service_identity"] == {
        "gid": 10001,
        "home": "/home/hadoop",
        "initialization_user": "root",
        "shell": "/bin/bash",
        "uid": 10001,
        "user": "hadoop",
    }
    assert inventory["spark"]["release"].startswith("Spark 3.5.4")
    assert inventory["process_tools"]["ps"].endswith("/ps")
    assert inventory["java"]["keytool"]
    assert inventory["python"]["ca_paths"]["cafile"] == "/etc/pki/tls/cert.pem"

    created = emr.run_job_flow(
        Name="prestart-environment-e2e",
        Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
        Applications=[{"Name": "Spark"}],
        BootstrapActions=[
            {
                "Name": "observe-prestart-environment",
                "ScriptBootstrapAction": {
                    "Path": f"s3://{bucket}/inputs/bootstrap.sh",
                    "Args": [bucket],
                },
            }
        ],
    )
    cluster_id = created["JobFlowId"]
    _wait_for_cluster(emr, cluster_id, {"WAITING"}, e2e_settings)
    bootstrap = s3.get_object(Bucket=bucket, Key="results/prestart-bootstrap.txt")["Body"].read()
    assert bootstrap == (
        b"runtime_user=hadoop\n"
        b"prestart_marker=trusted-root-environment-reached-hadoop\n"
        b"java_tool_options_present=true\n"
    )

    step_id = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "observe-prestart-in-spark",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit",
                        f"s3://{bucket}/inputs/spark.py",
                        "--output",
                        f"s3a://{bucket}/results/spark-json",
                    ],
                },
            }
        ],
    )["StepIds"][0]
    step = _wait_for_step(emr, cluster_id, step_id, {"COMPLETED", "FAILED"}, e2e_settings)
    assert step["Status"]["State"] == "COMPLETED", step["Status"]
    row = _first_json_row(s3, bucket, "results/spark-json/")
    assert row == {
        "id": 0,
        "java_tool_options_present": True,
        "prestart_marker": _MARKER,
        "runtime_user": "hadoop",
    }


@pytest.mark.e2e
def test_prestart_failure_is_fail_fast_and_default_entrypoint_is_signal_safe(
    e2e_settings: Any,
) -> None:
    _require_prestart()
    image = _compose(e2e_settings, ["images", "--quiet", e2e_settings.emr_service]).stdout.strip()
    assert image
    assets = Path(__file__).parent / "assets"

    failed_name = f"mystack-prestart-fail-{uuid.uuid4().hex}"
    try:
        created = _docker(
            e2e_settings,
            [
                "create",
                "--name",
                failed_name,
                "--env",
                "MYSTACK_EMR_PRESTART_ENABLED=true",
                "--env",
                "MYSTACK_EMR_PRESTART_DIR=/tmp/hooks",
                image,
            ],
        )
        assert created.returncode == 0, created.stderr
        copied = _docker(
            e2e_settings,
            ["cp", str(assets / "emr-prestart-fail.d"), f"{failed_name}:/tmp/hooks"],
        )
        assert copied.returncode == 0, copied.stderr
        started = _docker(e2e_settings, ["start", "--attach", failed_name])
        assert started.returncode == 23, started.stderr
        assert '"event":"emr.prestart.script.failed"' in started.stderr
        assert '"script":"10-fail.sh"' in started.stderr
        assert "20-must-not-run.sh" not in started.stderr
    finally:
        _docker(e2e_settings, ["rm", "--force", failed_name])

    signal_name = f"mystack-entrypoint-signal-{uuid.uuid4().hex}"
    try:
        created = _docker(e2e_settings, ["create", "--name", signal_name, image])
        assert created.returncode == 0, created.stderr
        assert _docker(e2e_settings, ["start", signal_name]).returncode == 0
        _wait_for_log(signal_name, "Application startup complete", e2e_settings)
        identity = _docker(
            e2e_settings,
            [
                "exec",
                signal_name,
                "python3.11",
                "-c",
                "import os; assert os.stat('/proc/1').st_uid == 10001",
            ],
        )
        assert identity.returncode == 0, identity.stderr
        stopped = _docker(e2e_settings, ["stop", "--time", "10", signal_name])
        assert stopped.returncode == 0, stopped.stderr
        exit_code = _docker(
            e2e_settings,
            ["inspect", "--format", "{{.State.ExitCode}}", signal_name],
        )
        assert exit_code.stdout.strip() == "0"
    finally:
        _docker(e2e_settings, ["rm", "--force", signal_name])


def _require_prestart() -> None:
    if os.getenv("MYSTACK_PRESTART_E2E_REQUIRED", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Start the stack with compose.emr-prestart.yaml to run this contract")


def _compose(settings: Any, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return _docker(settings, ["compose", "--file", str(settings.compose_file), *arguments])


def _docker(settings: Any, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        cwd=settings.compose_file.parent,
        capture_output=True,
        text=True,
        timeout=settings.timeout_seconds,
        check=False,
    )


def _wait_for_log(container: str, expected: str, settings: Any) -> None:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        logs = _docker(settings, ["logs", container])
        if expected in logs.stdout or expected in logs.stderr:
            return
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Container {container} did not log {expected!r}")


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
) -> dict[str, Any]:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        step = client.describe_step(ClusterId=cluster_id, StepId=step_id)["Step"]
        if step["Status"]["State"] in states:
            return step
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Step {step_id} did not enter {sorted(states)}")


def _first_json_row(client: Any, bucket: str, prefix: str) -> dict[str, Any]:
    objects = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    keys = {value["Key"] for value in objects.get("Contents", ())}
    assert f"{prefix}_SUCCESS" in keys
    data_key = next(key for key in keys if key.endswith(".json"))
    return json.loads(client.get_object(Bucket=bucket, Key=data_key)["Body"].read().splitlines()[0])
