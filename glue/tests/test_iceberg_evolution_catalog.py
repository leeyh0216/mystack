"""Lossless Glue pointer contracts for Iceberg metadata evolution.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
- https://iceberg.apache.org/spec/#table-metadata
- https://iceberg.apache.org/docs/1.7.1/evolution/
"""

from __future__ import annotations

from typing import Any

from tests.support.glue_error_harness import GlueCatalogHarness


def _table_input(metadata_version: int) -> dict[str, Any]:
    columns_by_version = {
        0: [
            {"Name": "id", "Type": "int"},
            {"Name": "category", "Type": "string"},
        ],
        1: [
            {"Name": "id", "Type": "bigint"},
            {"Name": "category_name", "Type": "string"},
            {"Name": "event", "Type": "struct<status_code:int,message:string>"},
        ],
        2: [
            {"Name": "id", "Type": "bigint"},
            {"Name": "category_name", "Type": "string"},
            {"Name": "event", "Type": "struct<status_code:int,message:string>"},
            {"Name": "amount", "Type": "decimal(12,2)"},
        ],
    }
    return {
        "Name": "events",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": (
                f"s3://warehouse/events/metadata/{metadata_version:05d}-metadata.json"
            ),
            "format-version": "2",
            "write.metadata.previous-versions-max": "100",
        },
        "StorageDescriptor": {
            "Columns": columns_by_version[metadata_version],
            "Location": "s3://warehouse/events",
        },
    }


def test_iceberg_metadata_evolution_pointers_are_lossless_and_versioned() -> None:
    catalog = GlueCatalogHarness()
    try:
        catalog.require_success(
            "CreateDatabase",
            {"DatabaseInput": {"Name": "analytics"}},
        )
        catalog.require_success(
            "CreateTable",
            {"DatabaseName": "analytics", "TableInput": _table_input(0)},
        )

        for expected_version, metadata_version in (("0", 1), ("1", 2)):
            catalog.require_success(
                "UpdateTable",
                {
                    "DatabaseName": "analytics",
                    "TableInput": _table_input(metadata_version),
                    "VersionId": expected_version,
                },
            )

        current = catalog.require_success(
            "GetTable",
            {"DatabaseName": "analytics", "Name": "events"},
        )["Table"]
        assert current["VersionId"] == "2"
        assert current["Parameters"] == _table_input(2)["Parameters"]
        assert current["StorageDescriptor"] == _table_input(2)["StorageDescriptor"]
        assert "PartitionKeys" not in current

        versions = catalog.require_success(
            "GetTableVersions",
            {"DatabaseName": "analytics", "TableName": "events"},
        )["TableVersions"]
        assert [version["VersionId"] for version in versions] == ["0", "1", "2"]
        assert [version["Table"]["Parameters"]["metadata_location"] for version in versions] == [
            _table_input(metadata_version)["Parameters"]["metadata_location"]
            for metadata_version in range(3)
        ]

        before_conflict = catalog.durable_state()
        conflict = catalog.call(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input(1),
                "VersionId": "0",
            },
        )
        assert conflict.status_code == 400
        assert conflict.json()["__type"] == "ConcurrentModificationException"
        assert catalog.durable_state() == before_conflict
    finally:
        catalog.close()
