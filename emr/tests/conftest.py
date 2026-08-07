"""EMR test fixtures with explicit, configurable timeouts.

References:
- https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
- https://docs.pytest.org/en/stable/how-to/fixtures.html
"""

from __future__ import annotations

import copy
import os
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import boto3
import pytest
import uvicorn
from botocore.config import Config
from mystack_aws_protocol import LoadedConfiguration, load_configuration
from mystack_emr.adapters.outbound import (
    AsyncioTaskScheduler,
    InMemoryClusterRepository,
    RandomAwsIds,
    SystemClock,
)
from mystack_emr.app import create_app
from mystack_emr.application import EmrApplication
from mystack_emr.application.ports import RuntimeResult
from mystack_emr.config import EmrSettings


@dataclass(slots=True)
class ControllableRuntime:
    block_steps: bool = False
    started: threading.Event = field(default_factory=threading.Event, init=False)
    cancelled: threading.Event = field(default_factory=threading.Event, init=False)

    async def run(self, cluster, value) -> RuntimeResult:
        del cluster
        if isinstance(value, tuple):
            return RuntimeResult(True, exit_code=0)
        self.started.set()
        if self.block_steps:
            while not self.cancelled.is_set():
                import asyncio

                await asyncio.sleep(0.01)
        return RuntimeResult(True, exit_code=0)

    async def cancel(self, cluster_id: str, step_id: str) -> None:
        del cluster_id, step_id
        self.cancelled.set()

    async def cleanup(self, cluster_id: str) -> None:
        del cluster_id
        self.cancelled.set()


@pytest.fixture
def test_timeout() -> float:
    return float(os.getenv("MYSTACK_TEST_TIMEOUT_SECONDS", "10"))


@pytest.fixture
def emr_server(
    tmp_path: Path,
    test_timeout: float,
) -> Iterator[tuple[str, ControllableRuntime]]:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["emr"]["work_root"] = str(tmp_path)
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"test-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )
    settings = EmrSettings.from_configuration(configured)
    repository = InMemoryClusterRepository()
    runtime = ControllableRuntime()
    application = EmrApplication(
        repository=repository,
        clock=SystemClock(),
        ids=RandomAwsIds(),
        bootstrap_runner=runtime,
        step_runner=runtime,
        scheduler=AsyncioTaskScheduler(),
        policy=settings.policy,
    )
    app = create_app(configuration=configured, application=application)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="emr-contract-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + test_timeout
    while not server.started:
        if time.monotonic() >= deadline:
            raise TimeoutError("EMR contract server did not start within the configured timeout")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}", runtime
    finally:
        server.should_exit = True
        thread.join(timeout=test_timeout)
        if thread.is_alive():
            raise TimeoutError("EMR contract server did not stop within the configured timeout")


@pytest.fixture
def emr_client(emr_server, test_timeout: float):
    endpoint_url, _ = emr_server
    return boto3.client(
        "emr",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=test_timeout,
            read_timeout=test_timeout,
            retries={"max_attempts": 0},
        ),
    )


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


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
