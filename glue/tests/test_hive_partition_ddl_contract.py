"""Glue operation contracts used by Spark 3.5 Hive partition DDL.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html
"""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError


@pytest.mark.contract
def test_hive_partition_ddl_operation_sequence_is_deterministic(glue_client) -> None:
    database = "hive_ddl"
    table = "events"
    glue_client.create_database(DatabaseInput={"Name": database})
    glue_client.create_table(
        DatabaseName=database,
        TableInput={
            "Name": table,
            "StorageDescriptor": {
                "Columns": [{"Name": "id", "Type": "bigint"}],
                "Location": "s3://warehouse/hive_ddl/events",
            },
            "PartitionKeys": [
                {"Name": "day", "Type": "date"},
                {"Name": "region", "Type": "string"},
            ],
        },
    )
    complex_partition = _partition(
        "2026-08-01",
        "ap/northeast=2",
        "s3://warehouse/hive_ddl/events/complex",
    )
    glue_client.create_partition(
        DatabaseName=database,
        TableName=table,
        PartitionInput=complex_partition,
    )

    batch = glue_client.batch_create_partition(
        DatabaseName=database,
        TableName=table,
        PartitionInputList=[
            complex_partition,
            _partition("2026-08-02", "west", "s3://warehouse/hive_ddl/events/rename"),
            _partition("2026-08-03", "drop", "s3://warehouse/hive_ddl/events/drop"),
        ],
    )
    assert [value["ErrorDetail"]["ErrorCode"] for value in batch["Errors"]] == [
        "AlreadyExistsException"
    ]

    glue_client.update_partition(
        DatabaseName=database,
        TableName=table,
        PartitionValueList=["2026-08-02", "west"],
        PartitionInput=_partition(
            "2026-08-20",
            "west",
            "s3://warehouse/hive_ddl/events/rename",
        ),
    )
    glue_client.update_partition(
        DatabaseName=database,
        TableName=table,
        PartitionValueList=["2026-08-20", "west"],
        PartitionInput=_partition(
            "2026-08-20",
            "west",
            "s3://warehouse/hive_ddl/events/location-updated",
        ),
    )
    with pytest.raises(ClientError) as collision:
        glue_client.update_partition(
            DatabaseName=database,
            TableName=table,
            PartitionValueList=["2026-08-03", "drop"],
            PartitionInput=_partition(
                "2026-08-20",
                "west",
                "s3://warehouse/hive_ddl/events/collision",
            ),
        )
    assert collision.value.response["Error"]["Code"] == "AlreadyExistsException"

    deleted = glue_client.batch_delete_partition(
        DatabaseName=database,
        TableName=table,
        PartitionsToDelete=[
            {"Values": ["2026-08-03", "drop"]},
            {"Values": ["1900-01-01", "missing"]},
        ],
    )
    assert [value["ErrorDetail"]["ErrorCode"] for value in deleted["Errors"]] == [
        "EntityNotFoundException"
    ]

    partitions = glue_client.get_partitions(DatabaseName=database, TableName=table)["Partitions"]
    by_values = {tuple(value["Values"]): value for value in partitions}
    assert set(by_values) == {
        ("2026-08-01", "ap/northeast=2"),
        ("2026-08-20", "west"),
    }
    assert by_values[("2026-08-20", "west")]["StorageDescriptor"]["Location"].endswith(
        "/location-updated"
    )
    assert glue_client.get_table(DatabaseName=database, Name=table)["Table"]["VersionId"] == "0"


def _partition(day: str, region: str, location: str) -> dict:
    return {
        "Values": [day, region],
        "StorageDescriptor": {
            "Columns": [{"Name": "id", "Type": "bigint"}],
            "Location": location,
        },
    }
