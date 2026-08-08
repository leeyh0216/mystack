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


@pytest.mark.contract
def test_get_partitions_combines_typed_expression_paging_and_segments(glue_client) -> None:
    """Exercise the public GetPartitions shape documented by AWS Glue.

    Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
    """
    glue_client.create_database(DatabaseInput={"Name": "pruning"})
    glue_client.create_table(
        DatabaseName="pruning",
        TableInput={
            "Name": "events",
            "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
            "PartitionKeys": [
                {"Name": "year", "Type": "int"},
                {"Name": "region", "Type": "string"},
                {"Name": "day", "Type": "date"},
            ],
        },
    )
    for values in (
        ["2025", "us-east-1", "2025-12-31"],
        ["2026", "ap-northeast-2", "2026-08-08"],
        ["2026", "ap-southeast-1", "2026-08-09"],
        ["2027", "eu-west-1", "2027-01-01"],
    ):
        glue_client.create_partition(
            DatabaseName="pruning",
            TableName="events",
            PartitionInput={"Values": values},
        )

    expression = "year BETWEEN 2026 AND 2027 AND region LIKE 'ap-%' AND NOT day < '2026-08-08'"
    first = glue_client.get_partitions(
        DatabaseName="pruning",
        TableName="events",
        Expression=expression,
        MaxResults=1,
    )
    second = glue_client.get_partitions(
        DatabaseName="pruning",
        TableName="events",
        Expression=expression,
        MaxResults=1,
        NextToken=first["NextToken"],
    )
    expected = {
        tuple(first["Partitions"][0]["Values"]),
        tuple(second["Partitions"][0]["Values"]),
    }
    assert expected == {
        ("2026", "ap-northeast-2", "2026-08-08"),
        ("2026", "ap-southeast-1", "2026-08-09"),
    }
    assert "NextToken" not in second

    segmented = []
    for segment_number in range(2):
        response = glue_client.get_partitions(
            DatabaseName="pruning",
            TableName="events",
            Expression=expression,
            Segment={"SegmentNumber": segment_number, "TotalSegments": 2},
        )
        segmented.append({tuple(value["Values"]) for value in response["Partitions"]})
    assert segmented[0].isdisjoint(segmented[1])
    assert segmented[0] | segmented[1] == expected
