"""Glue API contracts used by Iceberg rename, drop, and purge choreography.

Iceberg owns the multi-call operation. Its pinned GlueCatalog creates the destination, deletes the
source, and deletes the destination as compensation if source deletion fails. For purge it deletes
the Glue table before deleting files referenced by the loaded Iceberg metadata.

Official references:
- https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html
"""

from __future__ import annotations

from typing import Any

from test_support.glue_error_harness import GlueCatalogHarness, ToggleFailureStore


def _table_input(name: str, metadata_name: str) -> dict[str, Any]:
    return {
        "Name": name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": f"s3://warehouse/events/metadata/{metadata_name}.json",
            "format-version": "2",
        },
        "StorageDescriptor": {
            "Columns": [
                {"Name": "id", "Type": "bigint"},
                {"Name": "payload", "Type": "string"},
            ],
            "Location": "s3://warehouse/events",
        },
    }


def _create_database(catalog: GlueCatalogHarness, name: str) -> None:
    catalog.require_success("CreateDatabase", {"DatabaseInput": {"Name": name}})


def _create_table(
    catalog: GlueCatalogHarness,
    database: str,
    definition: dict[str, Any],
) -> None:
    catalog.require_success(
        "CreateTable",
        {"DatabaseName": database, "TableInput": definition},
    )


def test_iceberg_rename_choreography_preserves_pointer_and_modeled_errors() -> None:
    catalog = GlueCatalogHarness()
    try:
        _create_database(catalog, "source")
        _create_database(catalog, "target")
        original = _table_input("events", "00000-created")
        _create_table(catalog, "source", original)

        missing = catalog.call("GetTable", {"DatabaseName": "source", "Name": "missing"})
        assert missing.status_code == 400
        assert missing.json()["__type"] == "EntityNotFoundException"

        same_normalized_name = catalog.call(
            "CreateTable",
            {"DatabaseName": "source", "TableInput": _table_input("EVENTS", "collision")},
        )
        assert same_normalized_name.status_code == 400
        assert same_normalized_name.json()["__type"] == "AlreadyExistsException"

        collision = _table_input("collision", "00000-collision")
        _create_table(catalog, "target", collision)
        existing_target = catalog.call(
            "CreateTable",
            {"DatabaseName": "target", "TableInput": _table_input("collision", "candidate")},
        )
        assert existing_target.status_code == 400
        assert existing_target.json()["__type"] == "AlreadyExistsException"

        renamed = _table_input("renamed", "00000-created")
        _create_table(catalog, "target", renamed)
        catalog.require_success("DeleteTable", {"DatabaseName": "source", "Name": "events"})

        destination = catalog.require_success(
            "GetTable",
            {"DatabaseName": "target", "Name": "renamed"},
        )["Table"]
        assert destination["VersionId"] == "0"
        assert destination["Parameters"] == original["Parameters"]
        assert destination["StorageDescriptor"] == original["StorageDescriptor"]
        deleted_source = catalog.call(
            "GetTable",
            {"DatabaseName": "source", "Name": "events"},
        )
        assert deleted_source.status_code == 400
        assert deleted_source.json()["__type"] == "EntityNotFoundException"
    finally:
        catalog.close()


def test_iceberg_rename_compensation_keeps_source_when_source_delete_fails() -> None:
    store = ToggleFailureStore()
    catalog = GlueCatalogHarness(store)
    try:
        _create_database(catalog, "source")
        _create_database(catalog, "target")
        original = _table_input("events", "00000-created")
        _create_table(catalog, "source", original)
        _create_table(catalog, "target", _table_input("renamed", "00000-created"))
        store.fail_on_attempt = store.save_attempts + 1

        failed_delete = catalog.call(
            "DeleteTable",
            {"DatabaseName": "source", "Name": "events"},
        )

        assert failed_delete.status_code == 500
        assert failed_delete.json() == {
            "__type": "InternalServiceException",
            "Message": "An internal Glue persistence error occurred.",
        }
        source = catalog.require_success(
            "GetTable",
            {"DatabaseName": "source", "Name": "events"},
        )["Table"]
        destination = catalog.require_success(
            "GetTable",
            {"DatabaseName": "target", "Name": "renamed"},
        )["Table"]
        assert source["Parameters"] == destination["Parameters"]

        # This is the compensation performed by pinned Iceberg GlueCatalog.renameTable.
        catalog.require_success("DeleteTable", {"DatabaseName": "target", "Name": "renamed"})
        source_after_compensation = catalog.require_success(
            "GetTable",
            {"DatabaseName": "source", "Name": "events"},
        )["Table"]
        assert source_after_compensation["Parameters"] == original["Parameters"]
        compensated_target = catalog.call(
            "GetTable",
            {"DatabaseName": "target", "Name": "renamed"},
        )
        assert compensated_target.status_code == 400
        assert compensated_target.json()["__type"] == "EntityNotFoundException"
    finally:
        catalog.close()


def test_delete_table_is_catalog_only_and_missing_retry_is_modeled() -> None:
    catalog = GlueCatalogHarness()
    try:
        _create_database(catalog, "source")
        _create_table(catalog, "source", _table_input("events", "00000-created"))

        catalog.require_success("DeleteTable", {"DatabaseName": "source", "Name": "events"})
        retry = catalog.call("DeleteTable", {"DatabaseName": "source", "Name": "events"})

        assert retry.status_code == 400
        assert retry.json()["__type"] == "EntityNotFoundException"
    finally:
        catalog.close()
