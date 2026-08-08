"""Boto3 contracts for stable, application, and unsafe Glue extension SPIs.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html
- https://docs.python.org/3/library/importlib.metadata.html#entry-points
"""

from __future__ import annotations

import copy
import re
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from types import MappingProxyType

import boto3
import pytest
import uvicorn
from botocore.config import Config
from botocore.exceptions import ClientError
from mystack_aws_protocol import AwsServiceError, LoadedConfiguration, load_configuration
from mystack_glue.app import create_app
from mystack_glue.extensions import LoadedExtensionFactory


class FakeExtensionRegistry:
    def __init__(self, factories: dict[tuple[str, str], object]) -> None:
        self._factories = factories

    def load(self, group: str, name: str) -> LoadedExtensionFactory:
        return LoadedExtensionFactory(
            factory=self._factories[(group, name)],
            distribution=f"test-{name}",
            distribution_version="1.0.0",
        )


def test_all_three_spis_access_the_same_managed_state_and_translate_an_error(
    tmp_path: Path,
    glue_test_timeout: float,
) -> None:
    seen: dict[str, tuple[str, ...]] = {}
    immutable_snapshot: list[bool] = []

    def stable_provider(context):
        class StableMiddleware:
            async def invoke(self, call, next_handler):
                try:
                    return await next_handler(call)
                except AwsServiceError as error:
                    if error.code != "AlreadyExistsException":
                        raise
                    payload = call.payload
                    values = tuple(map(str, payload["PartitionInput"]["Values"]))
                    snapshot = await context.catalog.get_partition(
                        context.default_catalog_id,
                        str(payload["DatabaseName"]),
                        str(payload["TableName"]),
                        values,
                    )
                    seen["stable"] = snapshot.values
                    immutable_snapshot.append(isinstance(snapshot.definition, MappingProxyType))
                    with pytest.raises(TypeError):
                        snapshot.definition["Values"] = ("changed",)
                    raise AwsServiceError(
                        error.code,
                        f"stable SPI observed existing partition {list(snapshot.values)!r}",
                        http_status=error.http_status,
                    ) from error

        return StableMiddleware()

    def application_provider(context):
        class ApplicationMiddleware:
            async def invoke(self, call, next_handler):
                try:
                    return await next_handler(call)
                except AwsServiceError as error:
                    if error.code != "AlreadyExistsException":
                        raise
                    payload = call.payload
                    values = tuple(map(str, payload["PartitionInput"]["Values"]))
                    partition = await context.application.get_partition(
                        context.default_catalog_id,
                        str(payload["DatabaseName"]),
                        str(payload["TableName"]),
                        values,
                    )
                    assert context.mystack_version == version("mystack-glue")
                    seen["application"] = partition.values
                    raise

        return ApplicationMiddleware()

    def unsafe_provider(context):
        class UnsafeMiddleware:
            async def invoke(self, call, next_handler):
                try:
                    return await next_handler(call)
                except AwsServiceError as error:
                    if error.code != "AlreadyExistsException":
                        raise
                    payload = call.payload
                    values = tuple(map(str, payload["PartitionInput"]["Values"]))
                    partition = await context.repository.get_partition(
                        context.settings.policy.default_catalog_id,
                        str(payload["DatabaseName"]),
                        str(payload["TableName"]),
                        values,
                    )
                    seen["unsafe"] = partition.values
                    assert context.mystack_version == version("mystack-glue")
                    raise

        return UnsafeMiddleware()

    configured = _extension_configuration(tmp_path)
    registry = FakeExtensionRegistry(
        {
            ("mystack.glue.extensions.stable.v1", "test-stable"): stable_provider,
            (
                "mystack.glue.extensions.application.v1",
                "test-application",
            ): application_provider,
            ("mystack.glue.extensions.unsafe.v1", "test-unsafe"): unsafe_provider,
        }
    )
    app = create_app(configuration=configured, extension_registry=registry)

    with _running_server(app, glue_test_timeout) as endpoint_url:
        client = boto3.client(
            "glue",
            endpoint_url=endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            config=Config(
                connect_timeout=glue_test_timeout,
                read_timeout=glue_test_timeout,
                retries={"max_attempts": 0},
            ),
        )
        client.create_database(DatabaseInput={"Name": "extensions"})
        client.create_table(
            DatabaseName="extensions",
            TableInput={
                "Name": "events",
                "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
                "PartitionKeys": [{"Name": "day", "Type": "string"}],
            },
        )
        partition = {
            "DatabaseName": "extensions",
            "TableName": "events",
            "PartitionInput": {"Values": ["2026-08-08"]},
        }
        client.create_partition(**partition)

        with pytest.raises(ClientError) as captured:
            client.create_partition(**partition)

    assert captured.value.response["Error"]["Code"] == "AlreadyExistsException"
    assert "stable SPI observed" in captured.value.response["Error"]["Message"]
    assert seen == {
        "stable": ("2026-08-08",),
        "application": ("2026-08-08",),
        "unsafe": ("2026-08-08",),
    }
    assert immutable_snapshot == [True]


def test_version_scoped_spis_reject_incompatible_versions(tmp_path: Path) -> None:
    configured = _extension_configuration(tmp_path)
    current_minor = ".".join(version("mystack-glue").split(".", maxsplit=2)[:2])
    configured.document["glue"]["extensions"]["providers"][1]["mystack_minor_version"] = "9.9"

    with pytest.raises(
        ValueError,
        match=rf"requires mystack_minor_version='{re.escape(current_minor)}'",
    ):
        create_app(configuration=configured, extension_registry=FakeExtensionRegistry({}))

    configured.document["glue"]["extensions"]["providers"][1]["mystack_minor_version"] = (
        current_minor
    )
    configured.document["glue"]["extensions"]["allow_unsafe"] = False

    with pytest.raises(ValueError, match="allow_unsafe is false"):
        create_app(configuration=configured, extension_registry=FakeExtensionRegistry({}))

    configured.document["glue"]["extensions"]["allow_unsafe"] = True
    configured.document["glue"]["extensions"]["providers"][2]["mystack_version"] = "0.0.0"

    with pytest.raises(ValueError, match="requires exact mystack_version"):
        create_app(configuration=configured, extension_registry=FakeExtensionRegistry({}))


def _extension_configuration(tmp_path: Path) -> LoadedConfiguration:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path)
    document["glue"]["extensions"] = {
        "enabled": True,
        "allow_unsafe": True,
        "wheels_directory": str(tmp_path / "wheels"),
        "install_directory": str(tmp_path / "installed"),
        "install_timeout_seconds": 5,
        "providers": [
            {
                "id": "test-stable",
                "spi": "stable",
                "api_version": 1,
                "entry_point": "test-stable",
                "operations": ["CreatePartition"],
                "priority": 10,
                "timeout_seconds": 2,
            },
            {
                "id": "test-application",
                "spi": "application",
                "api_version": 1,
                "entry_point": "test-application",
                "operations": ["CreatePartition"],
                "priority": 20,
                "timeout_seconds": 2,
                "mystack_minor_version": ".".join(
                    version("mystack-glue").split(".", maxsplit=2)[:2]
                ),
            },
            {
                "id": "test-unsafe",
                "spi": "unsafe",
                "api_version": 1,
                "entry_point": "test-unsafe",
                "operations": ["CreatePartition"],
                "priority": 30,
                "timeout_seconds": 2,
                "mystack_version": version("mystack-glue"),
            },
        ],
    }
    return LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"extensions-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )


@contextmanager
def _running_server(app, timeout: float) -> Iterator[str]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="glue-extension-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while not server.started:
        if time.monotonic() >= deadline:
            raise TimeoutError("Glue extension server did not start within the configured timeout")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise TimeoutError("Glue extension server did not stop within the configured timeout")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
