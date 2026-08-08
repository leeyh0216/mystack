"""Complete implemented Glue Data Catalog boto3 scenario.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
"""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

_COLUMNS = [
    {"Name": "boolean_value", "Type": "boolean"},
    {"Name": "tinyint_value", "Type": "tinyint"},
    {"Name": "smallint_value", "Type": "smallint"},
    {"Name": "int_value", "Type": "int"},
    {"Name": "bigint_value", "Type": "bigint"},
    {"Name": "float_value", "Type": "float"},
    {"Name": "double_value", "Type": "double"},
    {"Name": "decimal_value", "Type": "decimal(38,18)"},
    {"Name": "string_value", "Type": "string"},
    {"Name": "char_value", "Type": "char(10)"},
    {"Name": "varchar_value", "Type": "varchar(20)"},
    {"Name": "binary_value", "Type": "binary"},
    {"Name": "date_value", "Type": "date"},
    {"Name": "timestamp_value", "Type": "timestamp"},
    {"Name": "nested_value", "Type": "array<struct<id:bigint,tags:map<string,string>>>"},
    {"Name": "map_value", "Type": "map<string,array<int>>"},
    {"Name": "union_value", "Type": "struct<a:int,b:uniontype<string,int>>"},
]


def exercise_all_glue_catalog_operations(client: Any, namespace: str) -> None:
    """Exercise every operation registered by GlueAwsAdapter through one boto3 client."""

    analytics = f"{namespace}_analytics"
    partitioned = f"{namespace}_partitioned"
    cascade = f"{namespace}_cascade"

    assert any(value["Name"] == "default" for value in client.get_databases()["DatabaseList"])
    client.create_database(
        DatabaseInput={
            "Name": analytics,
            "Description": "contract",
            "LocationUri": f"s3://warehouse/{analytics}",
        }
    )
    database = client.get_database(Name=analytics)["Database"]
    assert database["Name"] == analytics
    assert client.get_databases(MaxResults=1).get("NextToken")
    client.update_database(
        Name=analytics,
        DatabaseInput={"Name": analytics, "Description": "updated database"},
    )
    assert client.get_database(Name=analytics)["Database"]["Description"] == "updated database"

    table_input = {
        "Name": "events",
        "Owner": "mystack",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "parquet",
            "table_type": "ICEBERG",
            "metadata_location": f"s3://warehouse/{analytics}/events/metadata/v1.json",
        },
        "PartitionKeys": [{"Name": "day", "Type": "date"}],
        "StorageDescriptor": {
            "Columns": _COLUMNS,
            "Location": f"s3://warehouse/{analytics}/events",
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": (
                    "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                )
            },
        },
    }
    client.create_table(DatabaseName=analytics, TableInput=table_input)
    table = client.get_table(DatabaseName=analytics, Name="events")["Table"]
    assert table["StorageDescriptor"]["Columns"] == _COLUMNS
    assert table["Parameters"]["table_type"] == "ICEBERG"
    assert (
        client.get_tables(DatabaseName=analytics, Expression="event.*")["TableList"][0]["Name"]
        == "events"
    )
    assert client.get_tables(DatabaseName=analytics, AttributesToGet=["NAME", "TABLE_TYPE"])[
        "TableList"
    ] == [{"Name": "events", "TableType": "EXTERNAL_TABLE"}]

    updated_input = {**table_input, "Description": "updated"}
    client.update_table(
        DatabaseName=analytics,
        TableInput=updated_input,
        VersionId=table["VersionId"],
    )
    versions = client.get_table_versions(DatabaseName=analytics, TableName="events")[
        "TableVersions"
    ]
    assert [value["VersionId"] for value in versions] == ["0", "1"]
    assert (
        client.get_table_version(
            DatabaseName=analytics,
            TableName="events",
            VersionId="0",
        )["TableVersion"]["Table"].get("Description")
        is None
    )
    with pytest.raises(ClientError) as mismatch:
        client.update_table(
            DatabaseName=analytics,
            TableInput=updated_input,
            VersionId="0",
        )
        assert mismatch.value.response["Error"]["Code"] == "ConcurrentModificationException"
    assert client.get_catalog_import_status()["ImportStatus"]["ImportCompleted"] is True

    client.create_table(DatabaseName=analytics, TableInput={"Name": "disposable"})
    client.delete_table(DatabaseName=analytics, Name="disposable")
    with pytest.raises(ClientError) as deleted:
        client.get_table(DatabaseName=analytics, Name="disposable")
    assert deleted.value.response["Error"]["Code"] == "EntityNotFoundException"

    client.create_database(DatabaseInput={"Name": partitioned})
    client.create_table(
        DatabaseName=partitioned,
        TableInput={
            "Name": "events",
            "PartitionKeys": [
                {"Name": "day", "Type": "date"},
                {"Name": "region", "Type": "string"},
            ],
            "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
        },
    )
    first = {
        "Values": ["2026-08-08", "ap-northeast-2"],
        "StorageDescriptor": {
            "Columns": [{"Name": "id", "Type": "bigint"}],
            "Location": f"s3://warehouse/{partitioned}/day=2026-08-08/region=ap-northeast-2",
        },
    }
    client.create_partition(DatabaseName=partitioned, TableName="events", PartitionInput=first)
    with pytest.raises(ClientError) as duplicate:
        client.create_partition(
            DatabaseName=partitioned,
            TableName="events",
            PartitionInput=first,
        )
    assert duplicate.value.response["Error"]["Code"] == "AlreadyExistsException"
    assert duplicate.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400

    batch = client.batch_create_partition(
        DatabaseName=partitioned,
        TableName="events",
        PartitionInputList=[first, {"Values": ["2026-08-09", "us-east-1"]}],
    )
    assert batch["Errors"][0]["ErrorDetail"]["ErrorCode"] == "AlreadyExistsException"
    selected = client.get_partitions(
        DatabaseName=partitioned,
        TableName="events",
        Expression="day = '2026-08-09' AND region != 'ap-northeast-2'",
        ExcludeColumnSchema=True,
    )["Partitions"]
    assert [value["Values"] for value in selected] == [["2026-08-09", "us-east-1"]]
    assert "Columns" not in selected[0].get("StorageDescriptor", {})
    assert (
        len(
            client.batch_get_partition(
                DatabaseName=partitioned,
                TableName="events",
                PartitionsToGet=[
                    {"Values": ["2026-08-08", "ap-northeast-2"]},
                    {"Values": ["missing", "missing"]},
                ],
            )["Partitions"]
        )
        == 1
    )
    assert client.get_partition(
        DatabaseName=partitioned,
        TableName="events",
        PartitionValues=["2026-08-08", "ap-northeast-2"],
    )["Partition"]["Values"] == ["2026-08-08", "ap-northeast-2"]

    client.update_partition(
        DatabaseName=partitioned,
        TableName="events",
        PartitionValueList=["2026-08-09", "us-east-1"],
        PartitionInput={
            "Values": ["2026-08-10", "us-east-1"],
            "Parameters": {"updated": "true"},
        },
    )
    assert client.get_partition(
        DatabaseName=partitioned,
        TableName="events",
        PartitionValues=["2026-08-10", "us-east-1"],
    )["Partition"]["Parameters"] == {"updated": "true"}
    assert (
        client.batch_update_partition(
            DatabaseName=partitioned,
            TableName="events",
            Entries=[
                {
                    "PartitionValueList": ["missing", "missing"],
                    "PartitionInput": {"Values": ["missing", "missing"]},
                }
            ],
        )["Errors"][0]["ErrorDetail"]["ErrorCode"]
        == "EntityNotFoundException"
    )
    assert (
        client.batch_delete_partition(
            DatabaseName=partitioned,
            TableName="events",
            PartitionsToDelete=[
                {"Values": ["2026-08-10", "us-east-1"]},
                {"Values": ["missing", "missing"]},
            ],
        )["Errors"][0]["ErrorDetail"]["ErrorCode"]
        == "EntityNotFoundException"
    )
    client.delete_partition(
        DatabaseName=partitioned,
        TableName="events",
        PartitionValues=["2026-08-08", "ap-northeast-2"],
    )

    client.create_database(DatabaseInput={"Name": cascade})
    client.create_table(DatabaseName=cascade, TableInput={"Name": "table"})
    client.delete_database(Name=cascade)
    with pytest.raises(ClientError) as cascade_deleted:
        client.get_table(DatabaseName=cascade, Name="table")
    assert cascade_deleted.value.response["Error"]["Code"] == "EntityNotFoundException"

    client.delete_database(Name=analytics)
    client.delete_database(Name=partitioned)
