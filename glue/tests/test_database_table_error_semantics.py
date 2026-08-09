"""Database, table, and version error decisions through the AWS JSON boundary.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersion.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTables.html
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from test_support.glue_error_harness import GlueCatalogHarness, ToggleCommitFailpoint


@dataclass(frozen=True, slots=True)
class ErrorScenario:
    arrangement: str
    operation: str
    payload: dict
    error_code: str


@pytest.fixture
def catalog() -> GlueCatalogHarness:
    harness = GlueCatalogHarness()
    try:
        yield harness
    finally:
        harness.close()


@pytest.mark.parametrize(
    "scenario",
    (
        ErrorScenario(
            "database",
            "CreateDatabase",
            {"DatabaseInput": {"Name": "source"}},
            "AlreadyExistsException",
        ),
        ErrorScenario("empty", "GetDatabase", {"Name": "missing"}, "EntityNotFoundException"),
        ErrorScenario(
            "empty", "GetDatabases", {"NextToken": "not-a-token"}, "InvalidInputException"
        ),
        ErrorScenario("empty", "GetDatabases", {"MaxResults": 0}, "InvalidInputException"),
        ErrorScenario(
            "empty",
            "GetDatabases",
            {"AttributesToGet": ["TARGET_DATABASE"]},
            "InvalidInputException",
        ),
        ErrorScenario("empty", "GetDatabases", {"AttributesToGet": []}, "InvalidInputException"),
        ErrorScenario(
            "empty",
            "GetDatabases",
            {"AttributesToGet": ["NAME", "NAME"]},
            "InvalidInputException",
        ),
        ErrorScenario(
            "empty",
            "UpdateDatabase",
            {"Name": "missing", "DatabaseInput": {"Name": "renamed"}},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "UpdateDatabase",
            {"Name": "missing", "DatabaseInput": {"Name": "  "}},
            "InvalidInputException",
        ),
        ErrorScenario(
            "two_databases",
            "UpdateDatabase",
            {"Name": "source", "DatabaseInput": {"Name": "target"}},
            "AlreadyExistsException",
        ),
        ErrorScenario("empty", "DeleteDatabase", {"Name": "missing"}, "EntityNotFoundException"),
        ErrorScenario(
            "empty",
            "CreateTable",
            {"DatabaseName": "missing", "TableInput": {"Name": "events"}},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "table",
            "CreateTable",
            {"DatabaseName": "source", "TableInput": {"Name": "events"}},
            "AlreadyExistsException",
        ),
        ErrorScenario(
            "database",
            "GetTable",
            {"DatabaseName": "source", "Name": "missing"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "GetTables",
            {"DatabaseName": "missing"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "GetTables",
            {"DatabaseName": "missing", "Expression": "["},
            "InvalidInputException",
        ),
        ErrorScenario(
            "database",
            "GetTables",
            {"DatabaseName": "source", "Expression": "["},
            "InvalidInputException",
        ),
        ErrorScenario(
            "database",
            "GetTables",
            {"DatabaseName": "source", "AttributesToGet": ["TABLE_TYPE"]},
            "InvalidInputException",
        ),
        ErrorScenario(
            "database",
            "GetTables",
            {"DatabaseName": "source", "AttributesToGet": []},
            "InvalidInputException",
        ),
        ErrorScenario(
            "database",
            "GetTables",
            {"DatabaseName": "source", "AttributesToGet": ["NAME", "NAME"]},
            "InvalidInputException",
        ),
        ErrorScenario(
            "empty",
            "UpdateTable",
            {
                "DatabaseName": "missing",
                "Name": "missing",
                "TableInput": {"Name": "renamed"},
            },
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "UpdateTable",
            {
                "DatabaseName": "missing",
                "Name": "missing",
                "TableInput": {"Name": "  "},
            },
            "InvalidInputException",
        ),
        ErrorScenario(
            "two_tables",
            "UpdateTable",
            {
                "DatabaseName": "source",
                "Name": "events",
                "TableInput": {"Name": "target"},
                "VersionId": "99",
            },
            "AlreadyExistsException",
        ),
        ErrorScenario(
            "table",
            "UpdateTable",
            {
                "DatabaseName": "source",
                "Name": "events",
                "TableInput": {"Name": "events"},
                "VersionId": "99",
            },
            "ConcurrentModificationException",
        ),
        ErrorScenario(
            "database",
            "DeleteTable",
            {"DatabaseName": "source", "Name": "missing"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "GetTableVersion",
            {"DatabaseName": "missing", "TableName": "events"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "table",
            "GetTableVersion",
            {"DatabaseName": "source", "TableName": "events", "VersionId": "9"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "empty",
            "GetTableVersion",
            {"DatabaseName": "missing", "TableName": "events", "VersionId": "bad"},
            "InvalidInputException",
        ),
        ErrorScenario(
            "database",
            "GetTableVersions",
            {"DatabaseName": "source", "TableName": "missing"},
            "EntityNotFoundException",
        ),
        ErrorScenario(
            "database",
            "GetTableVersions",
            {
                "DatabaseName": "source",
                "TableName": "missing",
                "NextToken": "not-a-token",
            },
            "InvalidInputException",
        ),
        ErrorScenario(
            "table",
            "GetTableVersions",
            {
                "DatabaseName": "source",
                "TableName": "events",
                "NextToken": "not-a-token",
            },
            "InvalidInputException",
        ),
    ),
    ids=lambda scenario: f"{scenario.operation}-{scenario.error_code}",
)
def test_documented_error_decision_leaves_catalog_unchanged(
    catalog: GlueCatalogHarness,
    scenario: ErrorScenario,
) -> None:
    catalog.arrange(scenario.arrangement)
    before = catalog.durable_state()

    response = catalog.call(scenario.operation, scenario.payload)

    assert response.status_code == 400
    assert response.json()["__type"] == scenario.error_code
    assert catalog.durable_state() == before


def test_projection_archive_rename_and_cascade_semantics(catalog: GlueCatalogHarness) -> None:
    catalog.arrange("table")
    catalog.require_success(
        "CreatePartition",
        {
            "DatabaseName": "source",
            "TableName": "events",
            "PartitionInput": {"Values": ["2026-08-09"]},
        },
    )
    projected = catalog.require_success(
        "GetTables",
        {"DatabaseName": "source", "AttributesToGet": ["NAME", "TABLE_TYPE"]},
    )["TableList"]
    assert projected == [{"Name": "events"}]
    databases = catalog.require_success(
        "GetDatabases",
        {"AttributesToGet": ["NAME"]},
    )["DatabaseList"]
    assert databases == [{"Name": "source"}]

    catalog.require_success(
        "UpdateDatabase",
        {"Name": "source", "DatabaseInput": {"Name": "warehouse"}},
    )
    moved = catalog.require_success(
        "GetTable",
        {"DatabaseName": "warehouse", "Name": "events"},
    )["Table"]
    assert moved["DatabaseName"] == "warehouse"

    catalog.require_success(
        "UpdateTable",
        {
            "DatabaseName": "warehouse",
            "Name": "events",
            "TableInput": {
                "Name": "events",
                "Parameters": {"revision": "one"},
                "PartitionKeys": [{"Name": "day", "Type": "string"}],
            },
            "VersionId": "0",
        },
    )
    catalog.require_success(
        "UpdateTable",
        {
            "DatabaseName": "warehouse",
            "Name": "events",
            "TableInput": {
                "Name": "renamed",
                "Parameters": {"revision": "two"},
                "PartitionKeys": [{"Name": "day", "Type": "string"}],
            },
            "VersionId": "1",
            "SkipArchive": True,
        },
    )
    versions = catalog.require_success(
        "GetTableVersions",
        {"DatabaseName": "warehouse", "TableName": "renamed"},
    )["TableVersions"]
    assert [value["VersionId"] for value in versions] == ["0", "2"]
    partition = catalog.require_success(
        "GetPartition",
        {
            "DatabaseName": "warehouse",
            "TableName": "renamed",
            "PartitionValues": ["2026-08-09"],
        },
    )["Partition"]
    assert partition["TableName"] == "renamed"

    import_status = catalog.require_success("GetCatalogImportStatus", {})["ImportStatus"]
    assert import_status["ImportCompleted"] is True

    catalog.require_success("DeleteDatabase", {"Name": "warehouse"})
    state = catalog.durable_state()
    assert state.databases == {}
    assert state.tables == {}
    assert state.partitions == {}


def test_persistence_failure_is_internal_and_never_publishes_candidate() -> None:
    failpoint = ToggleCommitFailpoint()
    catalog = GlueCatalogHarness(failpoint)
    try:
        catalog.arrange("table")
        before = catalog.durable_state()
        failpoint.fail = True

        response = catalog.call(
            "UpdateTable",
            {
                "DatabaseName": "source",
                "Name": "events",
                "TableInput": {"Name": "renamed"},
                "VersionId": "0",
            },
        )

        assert response.status_code == 500
        assert response.json() == {
            "__type": "InternalServiceException",
            "Message": "An internal Glue persistence error occurred.",
        }
        assert catalog.durable_state() == before
    finally:
        catalog.close()
