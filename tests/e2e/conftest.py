"""Configurable E2E test harness.

References:
- https://docs.pytest.org/en/stable/how-to/mark.html
- https://github.com/pytest-dev/pytest-timeout
- https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.config import Config
from mystack_aws_protocol import LoadedConfiguration, load_configuration


@dataclass(frozen=True, slots=True)
class E2ESettings:
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    catalog_id: str
    timeout_seconds: float
    poll_interval_seconds: float
    sdk_connect_timeout_seconds: float
    sdk_read_timeout_seconds: float
    sdk_max_attempts: int
    browser_action_timeout_seconds: float
    browser_required_environment_variable: str
    compose_file: Path
    emr_service: str
    emr_jar_fixture_container_path: str
    emr_release_label: str
    emr_expected_spark_version_prefix: str
    glue_service: str
    glue_spark_submit: str
    glue_catalog_script: str
    glue_expected_spark_version_prefix: str
    glue_catalog_endpoint_url: str
    object_store_endpoint_url: str
    sts_endpoint_url: str
    artifacts_dir: Path

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> E2ESettings:
        tests = _mapping(loaded.document.get("tests"), "tests")
        e2e = _mapping(tests.get("e2e"), "tests.e2e")
        localstack = _mapping(loaded.document.get("localstack"), "localstack")
        source_root = Path(loaded.source).parent.parent
        compose_file = Path(str(e2e["compose_file"]))
        if not compose_file.is_absolute():
            compose_file = source_root / compose_file
        artifacts_dir = Path(str(e2e["artifacts_dir"]))
        if not artifacts_dir.is_absolute():
            artifacts_dir = source_root / artifacts_dir
        return cls(
            endpoint_url=str(e2e["endpoint_url"]),
            region=str(localstack["region"]),
            access_key_id=str(localstack["access_key_id"]),
            secret_access_key=str(localstack["secret_access_key"]),
            catalog_id=str(localstack["account_id"]),
            timeout_seconds=float(tests["e2e_timeout_seconds"]),
            poll_interval_seconds=float(e2e["poll_interval_seconds"]),
            sdk_connect_timeout_seconds=float(e2e["sdk_connect_timeout_seconds"]),
            sdk_read_timeout_seconds=float(e2e["sdk_read_timeout_seconds"]),
            sdk_max_attempts=int(e2e["sdk_max_attempts"]),
            browser_action_timeout_seconds=float(e2e["browser_action_timeout_seconds"]),
            browser_required_environment_variable=str(e2e["browser_required_environment_variable"]),
            compose_file=compose_file,
            emr_service=str(e2e["emr_service"]),
            emr_jar_fixture_container_path=str(e2e["emr_jar_fixture_container_path"]),
            emr_release_label=str(e2e["emr_release_label"]),
            emr_expected_spark_version_prefix=str(e2e["emr_expected_spark_version_prefix"]),
            glue_service=str(e2e["glue_service"]),
            glue_spark_submit=str(e2e["glue_spark_submit"]),
            glue_catalog_script=str(e2e["glue_catalog_script"]),
            glue_expected_spark_version_prefix=str(e2e["glue_expected_spark_version_prefix"]),
            glue_catalog_endpoint_url=str(e2e["glue_catalog_endpoint_url"]),
            object_store_endpoint_url=str(e2e["object_store_endpoint_url"]),
            sts_endpoint_url=str(e2e["sts_endpoint_url"]),
            artifacts_dir=artifacts_dir,
        )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every E2E case gets a timeout from the mounted config or env override."""

    settings = _load_settings()
    for item in items:
        if item.get_closest_marker("e2e") is not None:
            item.add_marker(pytest.mark.timeout(settings.timeout_seconds, method="thread"))


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    return _load_settings()


@pytest.fixture(scope="session")
def aws_clients(e2e_settings: E2ESettings) -> dict[str, Any]:
    session = boto3.Session(
        aws_access_key_id=e2e_settings.access_key_id,
        aws_secret_access_key=e2e_settings.secret_access_key,
        region_name=e2e_settings.region,
    )
    retry = Config(
        connect_timeout=e2e_settings.sdk_connect_timeout_seconds,
        read_timeout=e2e_settings.sdk_read_timeout_seconds,
        retries={"max_attempts": e2e_settings.sdk_max_attempts, "mode": "standard"},
    )
    return {
        "emr": session.client("emr", endpoint_url=e2e_settings.endpoint_url, config=retry),
        "glue": session.client("glue", endpoint_url=e2e_settings.endpoint_url, config=retry),
        "s3": session.client(
            "s3",
            endpoint_url=e2e_settings.endpoint_url,
            config=retry.merge(Config(s3={"addressing_style": "path"})),
        ),
    }


def _load_settings() -> E2ESettings:
    configured = os.getenv("MYSTACK_E2E_CONFIG_FILE") or os.getenv("MYSTACK_CONFIG_FILE")
    return E2ESettings.from_configuration(load_configuration(configured))


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section {path!r} must be a mapping")
    return value
