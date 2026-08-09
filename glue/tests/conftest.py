"""Real-port Glue boto3 fixtures with configurable timeouts.

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
from pathlib import Path

import boto3
import pytest
import uvicorn
from botocore.config import Config
from mystack.aws_protocol import LoadedConfiguration, load_configuration
from mystack.glue.app import create_app
from mystack.glue.application.ports import TableOptimizerExecutionResult

from tests.support.glue_error_harness import (
    IncrementingIdentifierGenerator,
    InMemoryIcebergMetadataStore,
)


@pytest.fixture
def glue_test_timeout() -> float:
    return float(os.getenv("MYSTACK_TEST_TIMEOUT_SECONDS", "10"))


@pytest.fixture
def glue_server(tmp_path: Path, glue_test_timeout: float) -> Iterator[str]:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path)
    # Unit/contract processes intentionally use the explicit rollback escape hatch. The source-
    # built WAL driver is verified in the Glue image preflight for both OCI architectures.
    document["glue"]["sqlite"]["journal_mode"] = "rollback"
    document["glue"]["sqlite"]["driver"]["module"] = "sqlite3"
    document["glue"]["table_optimizers"]["scheduler"]["initial_delay_seconds"] = 0
    document["glue"]["table_optimizers"]["scheduler"]["poll_interval_seconds"] = 0.01
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"test-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(
                configuration=configured,
                iceberg_metadata_store=InMemoryIcebergMetadataStore(),
                identifier_generator=IncrementingIdentifierGenerator(),
                table_optimizer_executor=ContractTableOptimizerExecutor(),
            ),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, name="glue-contract-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + glue_test_timeout
    while not server.started:
        if time.monotonic() >= deadline:
            raise TimeoutError("Glue contract server did not start within the configured timeout")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=glue_test_timeout)
        if thread.is_alive():
            raise TimeoutError("Glue contract server did not stop within the configured timeout")


@pytest.fixture
def glue_client(glue_server: str, glue_test_timeout: float):
    return boto3.client(
        "glue",
        endpoint_url=glue_server,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=glue_test_timeout,
            read_timeout=glue_test_timeout,
            retries={"max_attempts": 0},
        ),
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ContractTableOptimizerExecutor:
    async def execute(self, work) -> TableOptimizerExecutionResult:
        metrics = {
            "compaction": {"NumberOfBytesCompacted": 128, "NumberOfFilesCompacted": 2},
            "retention": {
                "NumberOfDataFilesDeleted": 1,
                "NumberOfManifestFilesDeleted": 1,
                "NumberOfManifestListsDeleted": 1,
            },
            "orphan_file_deletion": {"NumberOfOrphanFilesDeleted": 1},
        }[work.optimizer_type.value]
        return TableOptimizerExecutionResult(metrics)
