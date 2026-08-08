"""Glue pointer/error contract for Iceberg-owned row-level commits.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
- https://iceberg.apache.org/docs/1.7.1/spark-writes/
- https://iceberg.apache.org/spec/#snapshots
"""

from __future__ import annotations

from typing import Any

from test_support.glue_error_harness import GlueCatalogHarness


def _table_input(metadata_name: str, write_mode: str) -> dict[str, Any]:
    return {
        "Name": "orders",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": f"s3://warehouse/orders/metadata/{metadata_name}.json",
            "format-version": "2",
            "write.delete.mode": write_mode,
            "write.update.mode": write_mode,
            "write.merge.mode": write_mode,
        },
        "StorageDescriptor": {
            "Columns": [
                {"Name": "id", "Type": "bigint"},
                {"Name": "category", "Type": "string"},
                {"Name": "amount", "Type": "int"},
            ],
            "Location": "s3://warehouse/orders",
        },
    }


def test_stale_row_level_candidate_cannot_replace_last_committed_snapshot_pointer() -> None:
    catalog = GlueCatalogHarness()
    try:
        catalog.require_success(
            "CreateDatabase",
            {"DatabaseInput": {"Name": "analytics"}},
        )
        catalog.require_success(
            "CreateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("00000-initial", "merge-on-read"),
            },
        )
        catalog.require_success(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("00001-update-committed", "merge-on-read"),
                "VersionId": "0",
            },
        )

        before_conflict = catalog.durable_state()
        conflict = catalog.call(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("99999-stale-delete", "merge-on-read"),
                "VersionId": "0",
            },
        )

        assert conflict.status_code == 400
        assert conflict.json()["__type"] == "ConcurrentModificationException"
        assert catalog.durable_state() == before_conflict
        current = catalog.require_success(
            "GetTable",
            {"DatabaseName": "analytics", "Name": "orders"},
        )["Table"]
        assert current["VersionId"] == "1"
        assert (
            current["Parameters"]
            == _table_input("00001-update-committed", "merge-on-read")["Parameters"]
        )
        versions = catalog.require_success(
            "GetTableVersions",
            {"DatabaseName": "analytics", "TableName": "orders"},
        )["TableVersions"]
        assert [version["VersionId"] for version in versions] == ["0", "1"]
        assert all(
            "99999-stale-delete" not in version["Table"]["Parameters"]["metadata_location"]
            for version in versions
        )
    finally:
        catalog.close()
