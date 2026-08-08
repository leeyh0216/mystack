"""Black-box boto3 contracts for every implemented Glue Data Catalog operation.

API reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import httpx
import pytest

from test_support.glue_catalog import exercise_all_glue_catalog_operations


@pytest.mark.contract
def test_all_implemented_glue_operations_through_service_boundary(glue_client) -> None:
    exercise_all_glue_catalog_operations(glue_client, "contract")


@pytest.mark.contract
def test_management_read_model_lists_catalog_tree(
    glue_client,
    glue_server: str,
    glue_test_timeout: float,
) -> None:
    glue_client.create_database(DatabaseInput={"Name": "console"})
    glue_client.create_table(
        DatabaseName="console",
        TableInput={
            "Name": "events",
            "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
            "PartitionKeys": [{"Name": "day", "Type": "date"}],
        },
    )
    glue_client.create_partition(
        DatabaseName="console",
        TableName="events",
        PartitionInput={"Values": ["2026-08-08"]},
    )

    response = httpx.get(f"{glue_server}/_mystack/management/resources", timeout=glue_test_timeout)
    document = response.json()

    assert response.status_code == 200
    assert document["compatibility"]["implemented_operation_count"] == 22
    database = next(
        value for value in document["resources"]["databases"] if value["id"] == "console"
    )
    assert database["tables"][0]["partitions"][0]["values"] == ["2026-08-08"]
