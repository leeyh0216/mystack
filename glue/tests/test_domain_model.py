"""Glue aggregate invariant and lossless snapshot contracts.

References:
- https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
"""

from __future__ import annotations

import pytest
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    InvalidInputError,
    VersionMismatchError,
)


def test_catalog_name_and_document_are_normalized_defensive_snapshots() -> None:
    definition = {
        "Name": "  Events  ",
        "Description": "preserved",
        "Parameters": {"nested": "value"},
    }
    database = CatalogDatabase.create("account", definition, 1.0)
    definition["Parameters"]["nested"] = "mutated-input"
    exposed = database.definition
    exposed["Parameters"]["nested"] = "mutated-output"

    assert database.name == "events"
    assert database.definition == {
        "Name": "events",
        "Description": "preserved",
        "Parameters": {"nested": "value"},
    }
    with pytest.raises(InvalidInputError, match="cannot be empty"):
        CatalogDatabase.create("account", {"Name": "  "}, 1.0)


def test_table_owns_revision_archive_and_compare_and_swap() -> None:
    table = CatalogTable.create(
        "account",
        "db",
        {"Name": "events", "Parameters": {"revision": "zero"}},
        1.0,
    )

    revised = table.revise(
        {"Name": "events", "Parameters": {"revision": "one"}},
        now=2.0,
        expected_version_id="0",
        skip_archive=False,
    )

    assert table.version_id == "0"
    assert revised.version_id == "1"
    assert [version.version_id for version in revised.versions()] == ["0", "1"]
    assert revised.archived_versions[0].definition["Parameters"] == {"revision": "zero"}
    with pytest.raises(VersionMismatchError, match="current version is 1"):
        revised.revise(
            {"Name": "events"},
            now=3.0,
            expected_version_id="0",
            skip_archive=True,
        )


def test_skip_archive_changes_revision_without_adding_history() -> None:
    table = CatalogTable.create("account", "db", {"Name": "events"}, 1.0)

    revised = table.revise(
        {"Name": "events"},
        now=2.0,
        expected_version_id=None,
        skip_archive=True,
    )

    assert revised.version_id == "1"
    assert revised.archived_versions == ()


def test_partition_owns_value_count_and_defensive_document() -> None:
    definition = {"Values": ["2026", "08"], "Parameters": {"source": "test"}}
    partition = CatalogPartition.create(
        "account",
        "db",
        "events",
        definition,
        expected_value_count=2,
        now=1.0,
    )
    definition["Values"].append("unexpected")

    assert partition.values == ("2026", "08")
    assert partition.definition["Values"] == ["2026", "08"]
    with pytest.raises(InvalidInputError, match="table requires 1"):
        CatalogPartition.create(
            "account",
            "db",
            "events",
            {"Values": ["2026", "08"]},
            expected_value_count=1,
            now=1.0,
        )


def test_aggregate_moves_return_new_values_without_mutating_originals() -> None:
    table = CatalogTable.create("account", "old", {"Name": "events"}, 1.0)
    partition = CatalogPartition.create(
        "account",
        "old",
        "events",
        {"Values": []},
        expected_value_count=0,
        now=1.0,
    )

    moved_table = table.move_database("new")
    moved_partition = partition.move_database("new").move_table("renamed")

    assert (table.database_name, table.name) == ("old", "events")
    assert (moved_table.database_name, moved_table.name) == ("new", "events")
    assert (partition.database_name, partition.table_name) == ("old", "events")
    assert (moved_partition.database_name, moved_partition.table_name) == (
        "new",
        "renamed",
    )
