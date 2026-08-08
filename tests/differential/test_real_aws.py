"""Opt-in, read-only normalized comparisons between real AWS and Mystack.

References:
- https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
- https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_ListClusters.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetCatalogImportStatus.html
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore import xform_name
from botocore.config import Config
from botocore.exceptions import ClientError

DEFAULT_CONFIG = Path("contracts/differential-cases.json")


def _load_configuration() -> dict[str, Any]:
    path = Path(os.getenv("MYSTACK_DIFFERENTIAL_CONFIG", str(DEFAULT_CONFIG)))
    return json.loads(path.read_text(encoding="utf-8"))


_CONFIGURATION = _load_configuration()
_ENABLED = _CONFIGURATION["enabled"] or os.getenv(
    _CONFIGURATION["enable_environment_variable"], ""
).lower() in {"1", "true", "yes"}


@pytest.mark.differential
@pytest.mark.skipif(
    not _ENABLED,
    reason="real AWS differential contracts are opt-in and disabled by file configuration",
)
@pytest.mark.parametrize("case", _CONFIGURATION["cases"], ids=lambda case: case["name"])
def test_normalized_read_only_contract_against_real_aws(case: dict[str, Any]) -> None:
    timeout = float(
        os.getenv(
            _CONFIGURATION["timeout_environment_variable"],
            str(_CONFIGURATION["timeout_seconds"]),
        )
    )
    region = os.getenv(_CONFIGURATION["region_environment_variable"], _CONFIGURATION["region"])
    emulator_endpoint = os.getenv(
        _CONFIGURATION["emulator_endpoint_environment_variable"],
        _CONFIGURATION["emulator_endpoint_url"],
    )
    sdk_config = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"max_attempts": 0},
    )
    real_client = boto3.client(case["service"], region_name=region, config=sdk_config)
    emulator_client = boto3.client(
        case["service"],
        endpoint_url=emulator_endpoint,
        region_name=region,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=sdk_config,
    )

    real = _invoke(real_client, case)
    emulated = _invoke(emulator_client, case)

    assert emulated == real


def _invoke(client: Any, case: dict[str, Any]) -> dict[str, Any]:
    method = getattr(client, xform_name(case["operation"]))
    try:
        response = method(**case["request"])
    except ClientError as error:
        response = {
            "Error": error.response.get("Error", {}),
            "HTTPStatusCode": error.response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        }
        return {"outcome": "error", "response": _normalize(response, set(case["drop_keys"]))}
    return {
        "outcome": "success",
        "response": _normalize(response, set(case["drop_keys"])),
    }


def _normalize(value: Any, drop_keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize(child, drop_keys)
            for key, child in sorted(value.items())
            if key not in drop_keys
        }
    if isinstance(value, list):
        return [_normalize(child, drop_keys) for child in value]
    return value
