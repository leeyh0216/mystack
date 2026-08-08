"""Image-start EMR provisioning through boto3 and the management boundary.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/API_ListClusters.html
- https://docs.docker.com/reference/cli/docker/compose/restart/
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import httpx
import pytest
from botocore.exceptions import BotoCoreError, ClientError


@pytest.mark.e2e
def test_configured_cluster_exists_and_is_recreated_after_emr_restart(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    if os.getenv("MYSTACK_STARTUP_CLUSTER_E2E_REQUIRED", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("Start the stack with compose.emr-startup-clusters.yaml to run this contract")

    emr = aws_clients["emr"]
    first_id = _wait_for_named_cluster(emr, "preconfigured-e2e", e2e_settings)
    first = emr.describe_cluster(ClusterId=first_id)["Cluster"]
    assert first["Status"]["State"] == "WAITING"
    assert first["Applications"] == [{"Name": "Spark"}]
    _assert_management_resource(first_id, e2e_settings)

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

    second_id = _wait_for_named_cluster(
        emr,
        "preconfigured-e2e",
        e2e_settings,
        excluded_id=first_id,
    )
    assert second_id != first_id
    _assert_management_resource(second_id, e2e_settings)


def _wait_for_named_cluster(
    emr: Any,
    name: str,
    settings: Any,
    *,
    excluded_id: str | None = None,
) -> str:
    deadline = time.monotonic() + settings.timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            matches = [
                cluster
                for cluster in emr.list_clusters()["Clusters"]
                if cluster["Name"] == name and cluster["Id"] != excluded_id
            ]
            if len(matches) == 1 and matches[0]["Status"]["State"] == "WAITING":
                return str(matches[0]["Id"])
        except BotoCoreError as error:  # service restart deliberately interrupts a request
            last_error = error
        except ClientError as error:
            # Compose restart returns when PID 1 starts, before the pre-start boundary and EMR
            # listener are ready. Proxy returns a temporary 500 while its configured backend is
            # unavailable; other modeled service errors must still fail the contract immediately.
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 500:
                raise
            last_error = error
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(
        f"Cluster {name!r} was not uniquely discoverable after restart; last_error={last_error!r}"
    )


def _assert_management_resource(cluster_id: str, settings: Any) -> None:
    response = httpx.get(
        f"{settings.endpoint_url}/_mystack/components/emr/resources",
        timeout=settings.sdk_read_timeout_seconds,
    )
    response.raise_for_status()
    document = response.json()
    assert document["emulator"]["startup_clusters"]["configured_count"] == 1
    assert document["emulator"]["startup_clusters"]["fingerprint"]
    assert {cluster["id"] for cluster in document["resources"]["clusters"]} == {cluster_id}
