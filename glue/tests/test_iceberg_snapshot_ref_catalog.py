"""Glue pointer contracts for Iceberg snapshot/reference procedure commits.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
- https://iceberg.apache.org/docs/1.7.1/spark-procedures/
- https://iceberg.apache.org/spec/#table-metadata
"""

from __future__ import annotations

from typing import Any

from tests.support.glue_error_harness import GlueCatalogHarness
from tests.support.iceberg_metadata import IcebergMetadataDocument


def _table_input(metadata_name: str) -> dict[str, Any]:
    return {
        "Name": "events",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": f"s3://warehouse/events/metadata/{metadata_name}.json",
            "format-version": "2",
        },
        "StorageDescriptor": {
            "Columns": [
                {"Name": "id", "Type": "bigint"},
                {"Name": "category", "Type": "string"},
            ],
            "Location": "s3://warehouse/events",
        },
    }


def test_stale_snapshot_procedure_candidate_cannot_replace_current_pointer() -> None:
    catalog = GlueCatalogHarness()
    try:
        catalog.require_success("CreateDatabase", {"DatabaseInput": {"Name": "analytics"}})
        catalog.require_success(
            "CreateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("00000-created"),
            },
        )
        catalog.require_success(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("00001-snapshot-one"),
                "VersionId": "0",
            },
        )
        catalog.require_success(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("00002-set-current"),
                "VersionId": "1",
            },
        )

        before_conflict = catalog.durable_state()
        conflict = catalog.call(
            "UpdateTable",
            {
                "DatabaseName": "analytics",
                "TableInput": _table_input("99999-stale-rollback"),
                "VersionId": "1",
            },
        )

        assert conflict.status_code == 400
        assert conflict.json()["__type"] == "ConcurrentModificationException"
        assert catalog.durable_state() == before_conflict
        current = catalog.require_success(
            "GetTable",
            {"DatabaseName": "analytics", "Name": "events"},
        )["Table"]
        assert current["VersionId"] == "2"
        assert current["Parameters"] == _table_input("00002-set-current")["Parameters"]
        versions = catalog.require_success(
            "GetTableVersions",
            {"DatabaseName": "analytics", "TableName": "events"},
        )["TableVersions"]
        assert [version["VersionId"] for version in versions] == ["0", "1", "2"]
        assert all(
            "99999-stale-rollback" not in version["Table"]["Parameters"]["metadata_location"]
            for version in versions
        )
    finally:
        catalog.close()


def test_metadata_document_exposes_snapshot_references_without_list_position_coupling() -> None:
    metadata = IcebergMetadataDocument(
        {
            "current-snapshot-id": 202,
            "snapshots": [
                {"snapshot-id": 101, "summary": {"operation": "append"}},
                {"snapshot-id": 202, "summary": {"operation": "replace"}},
            ],
            "refs": {
                "main": {"snapshot-id": 202, "type": "branch"},
                "historical": {"snapshot-id": 101, "type": "tag"},
            },
        }
    )

    assert metadata.snapshot_ids() == {101, 202}
    assert metadata.reference_names() == {"main", "historical"}
    assert metadata.reference_snapshot_id("main") == 202
    assert metadata.reference_snapshot_id("historical") == 101
    assert metadata.snapshot_summary(101) == {"operation": "append"}
