# ruff: noqa: E501
"""Black-box boto3 contracts for every implemented Glue Data Catalog operation.

API reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import time

import httpx
import pytest
from mystack.glue.adapters.inbound.aws_operations import IMPLEMENTED_GLUE_OPERATIONS

from tests.support.compatibility import compatibility_evidence
from tests.support.compatibility_profiles import BOTO3_BOTOCORE_CONTRACT
from tests.support.glue_catalog import exercise_all_glue_catalog_operations


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-data-catalog", "modeled-service-errors"),
    operations={"glue": tuple(sorted(IMPLEMENTED_GLUE_OPERATIONS))},
    capabilities=("catalog-operation-boundary", "modeled-errors"),
)
def test_all_implemented_glue_operations_through_service_boundary(glue_client) -> None:
    exercise_all_glue_catalog_operations(glue_client, "contract")


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-data-catalog",),
    capabilities=("management-read-model",),
)
def test_management_read_model_pages_only_the_requested_catalog_branch(
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

    databases = httpx.get(
        f"{glue_server}/_mystack/ui/glue/catalog/databases?limit=1", timeout=glue_test_timeout
    )
    tables = httpx.get(
        f"{glue_server}/_mystack/ui/glue/catalog/databases/console/tables?limit=1",
        timeout=glue_test_timeout,
    )
    partitions = httpx.get(
        f"{glue_server}/_mystack/ui/glue/catalog/databases/console/tables/events/partitions?limit=1",
        timeout=glue_test_timeout,
    )

    assert databases.status_code == tables.status_code == partitions.status_code == 200
    assert databases.json()["items"][0]["id"] == "console"
    assert tables.json()["items"][0]["id"] == "console/events"
    assert partitions.json()["items"][0]["values"] == ["2026-08-08"]
    assert partitions.json()["total_count"] == 1


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-data-catalog",),
    capabilities=("typed-partition-expression", "pagination", "segments"),
)
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


@pytest.mark.contract
def test_managed_optimizer_run_shapes_through_boto3(
    glue_client,
    glue_test_timeout: float,
) -> None:
    glue_client.create_database(DatabaseInput={"Name": "optimizer_runs"})
    glue_client.create_table(
        DatabaseName="optimizer_runs",
        TableInput={
            "Name": "events",
            "Parameters": {
                "table_type": "ICEBERG",
                "metadata_location": "s3://warehouse/optimizer/events/metadata/v1.json",
            },
            "StorageDescriptor": {"Location": "s3://warehouse/optimizer/events"},
        },
    )
    expected_metric_keys = {
        "compaction": "compactionMetrics",
        "retention": "retentionMetrics",
        "orphan_file_deletion": "orphanFileDeletionMetrics",
    }
    for optimizer_type, metric_key in expected_metric_keys.items():
        glue_client.create_table_optimizer(
            CatalogId="000000000000",
            DatabaseName="optimizer_runs",
            TableName="events",
            Type=optimizer_type,
            TableOptimizerConfiguration={"enabled": True},
        )
        deadline = time.monotonic() + glue_test_timeout
        while time.monotonic() < deadline:
            runs = glue_client.list_table_optimizer_runs(
                CatalogId="000000000000",
                DatabaseName="optimizer_runs",
                TableName="events",
                Type=optimizer_type,
            )["TableOptimizerRuns"]
            if runs and runs[0]["eventType"] == "completed":
                break
            time.sleep(0.01)
        else:
            raise AssertionError(f"Optimizer {optimizer_type} exceeded contract timeout")
        assert runs[0][metric_key]["IcebergMetrics"]
