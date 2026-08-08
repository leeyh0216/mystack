"""Glue Open Table Format domain, wire, and compensation contracts.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateIcebergTableInput.html
- https://iceberg.apache.org/spec/#table-metadata
"""

from __future__ import annotations

import copy

import pytest
from botocore.exceptions import ClientError
from mystack.glue.domain import IcebergOpenTableFormatPlanner, InvalidInputError

from test_support.glue_error_harness import GlueCatalogHarness


def _schema(*, schema_id: int = 0, include_note: bool = False) -> dict:
    fields = [
        {"Id": 1, "Name": "id", "Type": "long", "Required": True},
        {
            "Id": 2,
            "Name": "payload",
            "Required": False,
            "Type": {
                "type": "struct",
                "fields": [{"id": 3, "name": "city", "type": "string", "required": False}],
            },
        },
    ]
    if include_note:
        fields.append({"Id": 4, "Name": "note", "Type": "string", "Required": False})
    return {
        "SchemaId": schema_id,
        "Type": "struct",
        "Fields": fields,
        "IdentifierFieldIds": [1],
    }


def _create_input() -> dict:
    return {
        "MetadataOperation": "CREATE",
        "Version": "2",
        "CreateIcebergTableInput": {
            "Location": "s3://warehouse/analytics/events",
            "Schema": _schema(),
            "PartitionSpec": {
                "SpecId": 0,
                "Fields": [
                    {
                        "SourceId": 1,
                        "FieldId": 1000,
                        "Name": "id_bucket",
                        "Transform": "bucket[16]",
                    }
                ],
            },
            "WriteOrder": {
                "OrderId": 1,
                "Fields": [
                    {
                        "SourceId": 1,
                        "Transform": "identity",
                        "Direction": "asc",
                        "NullOrder": "nulls-first",
                    }
                ],
            },
            "Properties": {"write.format.default": "parquet"},
        },
    }


def _update_input() -> dict:
    schema = _schema(schema_id=1, include_note=True)
    location = "s3://warehouse/analytics/events"
    return {
        "UpdateIcebergTableInput": {
            "Updates": [
                {"Action": "add-schema", "Schema": schema, "Location": location},
                {
                    "Action": "set-current-schema",
                    "Schema": schema,
                    "Location": location,
                },
                {
                    "Action": "set-properties",
                    "Schema": schema,
                    "Location": location,
                    "Properties": {"owner": "data-platform"},
                },
            ]
        }
    }


def test_planner_creates_complete_v2_metadata_for_nested_partitioned_table() -> None:
    plan = IcebergOpenTableFormatPlanner().create(
        table_name="Events",
        iceberg_input=_create_input(),
        now_ms=1234,
        identifier="00000000-0000-0000-0000-000000000001",
    )

    assert plan.metadata_location.endswith(
        "00000-00000000-0000-0000-0000-000000000001.metadata.json"
    )
    assert plan.metadata["format-version"] == 2
    assert plan.metadata["last-column-id"] == 3
    assert plan.metadata["partition-specs"][0]["fields"][0]["transform"] == "bucket[16]"
    assert plan.metadata["sort-orders"][0]["order-id"] == 1
    assert plan.table_definition["Name"] == "events"
    assert plan.table_definition["StorageDescriptor"]["Columns"] == [
        {"Name": "id", "Type": "bigint"},
        {"Name": "payload", "Type": "struct<city:string>"},
    ]


def test_planner_rejects_nested_field_id_reuse() -> None:
    value = _create_input()
    value["CreateIcebergTableInput"]["Schema"]["Fields"][1]["Type"]["fields"][0]["id"] = 2

    with pytest.raises(InvalidInputError, match="globally unique"):
        IcebergOpenTableFormatPlanner().create(
            table_name="events",
            iceberg_input=value,
            now_ms=1,
            identifier="id",
        )


def test_planner_rejects_identifier_under_optional_struct() -> None:
    value = _create_input()
    value["CreateIcebergTableInput"]["Schema"]["IdentifierFieldIds"] = [3]
    value["CreateIcebergTableInput"]["Schema"]["Fields"][1]["Type"]["fields"][0]["required"] = True

    with pytest.raises(InvalidInputError, match="outside optional"):
        IcebergOpenTableFormatPlanner().create(
            table_name="events",
            iceberg_input=value,
            now_ms=1,
            identifier="id",
        )


def test_planner_rejects_float_identifier_field() -> None:
    value = _create_input()
    value["CreateIcebergTableInput"]["Schema"]["Fields"][0]["Type"] = "double"

    with pytest.raises(InvalidInputError, match="required primitive"):
        IcebergOpenTableFormatPlanner().create(
            table_name="events",
            iceberg_input=value,
            now_ms=1,
            identifier="id",
        )


def test_planner_rejects_transform_incompatible_with_source_type() -> None:
    value = _create_input()
    value["CreateIcebergTableInput"]["PartitionSpec"]["Fields"][0]["Transform"] = "year"

    with pytest.raises(InvalidInputError, match="not valid for Iceberg type"):
        IcebergOpenTableFormatPlanner().create(
            table_name="events",
            iceberg_input=value,
            now_ms=1,
            identifier="id",
        )


def test_planner_applies_schema_partition_sort_property_and_location_actions() -> None:
    planner = IcebergOpenTableFormatPlanner()
    initial = planner.create(
        table_name="events",
        iceberg_input=_create_input(),
        now_ms=1,
        identifier="initial",
    )
    initial.metadata["current-snapshot-id"] = 10
    initial.metadata["snapshots"] = [{"snapshot-id": 10, "timestamp-ms": 1}]
    schema = _schema(schema_id=1, include_note=True)
    partition = {
        "SpecId": 1,
        "Fields": [
            {
                "SourceId": 4,
                "FieldId": 1001,
                "Name": "note_prefix",
                "Transform": "truncate[2]",
            }
        ],
    }
    order = {
        "OrderId": 2,
        "Fields": [
            {
                "SourceId": 4,
                "Transform": "identity",
                "Direction": "desc",
                "NullOrder": "nulls-last",
            }
        ],
    }
    location = "s3://warehouse/analytics/events-relocated"
    common = {"Schema": schema, "Location": location}
    updates = [
        {**common, "Action": "add-schema"},
        {**common, "Action": "set-current-schema"},
        {**common, "Action": "add-spec", "PartitionSpec": partition},
        {**common, "Action": "set-default-spec", "PartitionSpec": partition},
        {**common, "Action": "add-sort-order", "SortOrder": order},
        {**common, "Action": "set-default-sort-order", "SortOrder": order},
        {**common, "Action": "set-location"},
        {**common, "Action": "set-properties", "Properties": {"owner": "platform"}},
        {**common, "Action": "remove-properties", "Properties": {"owner": "ignored"}},
    ]

    revised = planner.update(
        table_definition=initial.table_definition,
        current_metadata_location=initial.metadata_location,
        current_metadata=initial.metadata,
        update_input={"UpdateIcebergTableInput": {"Updates": updates}},
        now_ms=2,
        identifier="revised",
    )

    assert revised.metadata["current-schema-id"] == 1
    assert revised.metadata["default-spec-id"] == 1
    assert revised.metadata["default-sort-order-id"] == 2
    assert revised.metadata["location"] == location
    assert "owner" not in revised.metadata["properties"]
    assert revised.metadata["snapshots"] == [{"snapshot-id": 10, "timestamp-ms": 1}]
    assert revised.metadata["metadata-log"][-1]["metadata-file"] == initial.metadata_location
    assert revised.metadata_location.startswith(f"{location}/metadata/00001-")


def test_planner_rejects_encryption_actions_for_local_glue_profile() -> None:
    planner = IcebergOpenTableFormatPlanner()
    initial = planner.create(
        table_name="events",
        iceberg_input=_create_input(),
        now_ms=1,
        identifier="initial",
    )

    with pytest.raises(InvalidInputError, match="encryption-key"):
        planner.update(
            table_definition=initial.table_definition,
            current_metadata_location=initial.metadata_location,
            current_metadata=initial.metadata,
            update_input={
                "UpdateIcebergTableInput": {
                    "Updates": [
                        {
                            "Action": "add-encryption-key",
                            "Schema": _schema(),
                            "Location": "s3://warehouse/analytics/events",
                        }
                    ]
                }
            },
            now_ms=2,
            identifier="revised",
        )


def test_boto3_open_table_format_create_and_update(glue_client) -> None:
    glue_client.create_database(DatabaseInput={"Name": "analytics"})
    glue_client.create_table(
        DatabaseName="analytics",
        Name="events",
        OpenTableFormatInput={"IcebergInput": _create_input()},
    )

    created = glue_client.get_table(DatabaseName="analytics", Name="events")["Table"]
    first_location = created["Parameters"]["metadata_location"]
    assert created["Parameters"]["table_type"] == "ICEBERG"
    assert created["StorageDescriptor"]["Columns"][1]["Type"] == "struct<city:string>"

    glue_client.update_table(
        DatabaseName="analytics",
        Name="events",
        VersionId=created["VersionId"],
        UpdateOpenTableFormatInput={"UpdateIcebergInput": _update_input()},
    )

    revised = glue_client.get_table(DatabaseName="analytics", Name="events")["Table"]
    assert revised["VersionId"] == "1"
    assert revised["Parameters"]["metadata_location"] != first_location
    assert revised["Parameters"]["previous_metadata_location"] == first_location
    assert revised["StorageDescriptor"]["Columns"][-1] == {
        "Name": "note",
        "Type": "string",
    }


@pytest.mark.parametrize("include_table_input", [False, True])
def test_create_requires_exactly_one_table_input(glue_client, include_table_input: bool) -> None:
    glue_client.create_database(DatabaseInput={"Name": "analytics"})
    request: dict = {"DatabaseName": "analytics"}
    if include_table_input:
        request.update(
            {
                "Name": "events",
                "TableInput": {"Name": "events"},
                "OpenTableFormatInput": {"IcebergInput": _create_input()},
            }
        )

    with pytest.raises(ClientError) as captured:
        glue_client.create_table(**request)

    assert captured.value.response["Error"]["Code"] == "InvalidInputException"


def test_catalog_failure_removes_unreferenced_metadata_candidate() -> None:
    catalog = GlueCatalogHarness()
    try:
        catalog.require_success("CreateDatabase", {"DatabaseInput": {"Name": "analytics"}})
        catalog.store.fail_on_attempt = catalog.store.save_attempts + 1
        response = catalog.call(
            "CreateTable",
            {
                "DatabaseName": "analytics",
                "Name": "events",
                "OpenTableFormatInput": {"IcebergInput": copy.deepcopy(_create_input())},
            },
        )

        assert response.status_code == 500
        assert response.json()["__type"] == "InternalServiceException"
        assert catalog.metadata_store.documents == {}
    finally:
        catalog.close()
