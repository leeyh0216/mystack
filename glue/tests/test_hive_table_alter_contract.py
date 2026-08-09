"""Glue API contracts used by Spark Hive table-level ALTER operations.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
- https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html
"""

from __future__ import annotations

import copy

import pytest
from botocore.exceptions import ClientError

from test_support.compatibility import compatibility_evidence
from test_support.compatibility_profiles import BOTO3_BOTOCORE_CONTRACT


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-data-catalog",),
    capabilities=("hive-table-alter", "table-versioning"),
)
def test_hive_table_alter_preserves_metadata_versions_and_partitions(glue_client) -> None:
    database = "hive_table_alter"
    source = "events"
    glue_client.create_database(DatabaseInput={"Name": database})
    original = _table_input(source)
    glue_client.create_table(DatabaseName=database, TableInput=original)
    glue_client.create_partition(
        DatabaseName=database,
        TableName=source,
        PartitionInput={
            "Values": ["2026-08-09"],
            "StorageDescriptor": copy.deepcopy(original["StorageDescriptor"]),
        },
    )

    altered = copy.deepcopy(original)
    altered["Description"] = "altered through the Hive metastore"
    altered["Parameters"] = {
        **altered["Parameters"],
        "mystack.contract": "table-alter",
    }
    altered["StorageDescriptor"]["Columns"] = [
        {"Name": "id", "Type": "bigint", "Comment": "stable identifier"},
        {"Name": "payload", "Type": "struct<kind:string,tags:array<string>>"},
        {"Name": "note", "Type": "string", "Comment": "added"},
    ]
    altered["StorageDescriptor"]["Location"] = "s3://warehouse/hive_table_alter/v2"
    altered["StorageDescriptor"]["SerdeInfo"]["Parameters"] = {"serialization.format": "1"}
    glue_client.update_table(
        DatabaseName=database,
        Name=source,
        TableInput=altered,
        VersionId="0",
    )

    current = glue_client.get_table(DatabaseName=database, Name=source)["Table"]
    assert current["VersionId"] == "1"
    assert current["Description"] == "altered through the Hive metastore"
    assert current["StorageDescriptor"] == altered["StorageDescriptor"]
    assert current["Parameters"] == altered["Parameters"]
    versions = glue_client.get_table_versions(DatabaseName=database, TableName=source)[
        "TableVersions"
    ]
    assert [value["VersionId"] for value in versions] == ["0", "1"]
    assert versions[0]["Table"]["StorageDescriptor"] == original["StorageDescriptor"]

    skipped = copy.deepcopy(altered)
    skipped["Parameters"]["transient_lastDdlTime"] = "1786233600"
    glue_client.update_table(
        DatabaseName=database,
        Name=source,
        TableInput=skipped,
        VersionId="1",
        SkipArchive=True,
    )
    versions = glue_client.get_table_versions(DatabaseName=database, TableName=source)[
        "TableVersions"
    ]
    assert [value["VersionId"] for value in versions] == ["0", "2"]

    glue_client.create_table(
        DatabaseName=database,
        TableInput={"Name": "occupied"},
    )
    collision = copy.deepcopy(skipped)
    collision["Name"] = "occupied"
    with pytest.raises(ClientError) as existing_target:
        glue_client.update_table(
            DatabaseName=database,
            Name=source,
            TableInput=collision,
            VersionId="2",
        )
    assert existing_target.value.response["Error"]["Code"] == "AlreadyExistsException"
    assert glue_client.get_table(DatabaseName=database, Name=source)["Table"]["VersionId"] == "2"

    renamed = copy.deepcopy(skipped)
    renamed["Name"] = "renamed_events"
    glue_client.update_table(
        DatabaseName=database,
        Name=source,
        TableInput=renamed,
        VersionId="2",
    )
    with pytest.raises(ClientError) as missing_old_name:
        glue_client.get_table(DatabaseName=database, Name=source)
    assert missing_old_name.value.response["Error"]["Code"] == "EntityNotFoundException"
    partition = glue_client.get_partition(
        DatabaseName=database,
        TableName="renamed_events",
        PartitionValues=["2026-08-09"],
    )["Partition"]
    assert partition["TableName"] == "renamed_events"
    assert [
        value["VersionId"]
        for value in glue_client.get_table_versions(
            DatabaseName=database,
            TableName="renamed_events",
        )["TableVersions"]
    ] == ["0", "2", "3"]

    case_only = copy.deepcopy(renamed)
    case_only["Name"] = "ReNaMeD_EvEnTs"
    glue_client.update_table(
        DatabaseName=database,
        Name="RENAMED_EVENTS",
        TableInput=case_only,
        VersionId="3",
    )
    normalized = glue_client.get_table(DatabaseName=database, Name="renamed_events")["Table"]
    assert normalized["Name"] == "renamed_events"
    assert normalized["VersionId"] == "4"

    missing = copy.deepcopy(renamed)
    missing["Name"] = "never_created"
    with pytest.raises(ClientError) as missing_source:
        glue_client.update_table(
            DatabaseName=database,
            Name="missing_source",
            TableInput=missing,
        )
    assert missing_source.value.response["Error"]["Code"] == "EntityNotFoundException"


def _table_input(name: str) -> dict:
    return {
        "Name": name,
        "Owner": "hadoop",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {"EXTERNAL": "TRUE", "classification": "parquet"},
        "PartitionKeys": [{"Name": "day", "Type": "date"}],
        "StorageDescriptor": {
            "Columns": [
                {"Name": "id", "Type": "bigint"},
                {"Name": "payload", "Type": "struct<kind:string,tags:array<string>>"},
            ],
            "Location": "s3://warehouse/hive_table_alter/v1",
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": (
                    "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                ),
                "Parameters": {"serialization.format": "0"},
            },
        },
    }
