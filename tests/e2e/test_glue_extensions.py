"""Mounted-wheel E2E for all three Glue extension SPI entry points.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html
- https://docs.python.org/3/library/importlib.metadata.html#entry-points
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from botocore.exceptions import ClientError


@pytest.mark.e2e
@pytest.mark.skipif(
    os.getenv("MYSTACK_GLUE_EXTENSION_E2E") != "1",
    reason="mounted Glue extension E2E is a separate opt-in stack",
)
def test_mounted_wheel_composes_stable_application_and_unsafe_spis(
    aws_clients: dict[str, Any],
) -> None:
    client = aws_clients["glue"]
    suffix = uuid.uuid4().hex[:10]
    database = f"extension_{suffix}"
    table = "events"
    client.create_database(DatabaseInput={"Name": database})
    client.create_table(
        DatabaseName=database,
        TableInput={
            "Name": table,
            "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
            "PartitionKeys": [{"Name": "day", "Type": "string"}],
        },
    )
    request = {
        "DatabaseName": database,
        "TableName": table,
        "PartitionInput": {"Values": ["2026-08-08"]},
    }
    client.create_partition(**request)

    with pytest.raises(ClientError) as captured:
        client.create_partition(**request)

    error = captured.value.response["Error"]
    assert error["Code"] == "AlreadyExistsException"
    assert "stable example observed existing partition" in error["Message"]
