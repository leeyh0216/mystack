"""Database, table, and version error decisions through the AWS JSON boundary.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersion.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetTables.html
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack.aws_protocol import AwsJsonRpcEndpoint, AwsServiceModel
from mystack.glue.adapters.inbound.aws import GlueAwsAdapter
from mystack.glue.adapters.outbound import CatalogStateStore, TransactionalCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.domain import CatalogState


@dataclass(frozen=True, slots=True)
class ErrorScenario:
    arrangement: str
    operation: str
    payload: dict
    error_code: str


class IncrementingClock:
    def __init__(self) -> None:
        self._value = 0.0

    def now(self) -> float:
        self._value += 1.0
        return self._value


class ToggleFailureStore(CatalogStateStore):
    def __init__(self) -> None:
        self._committed = CatalogState()
        self.fail = False

    def load(self) -> CatalogState:
        return copy.deepcopy(self._committed)

    async def save(self, candidate: CatalogState) -> None:
        if self.fail:
            raise OSError("deterministic test persistence failure")
        self._committed = copy.deepcopy(candidate)


class GlueCatalogHarness:
    """Compose real application/repository objects behind the shared wire controller."""

    def __init__(self, store: ToggleFailureStore | None = None) -> None:
        self.store = store or ToggleFailureStore()
        repository = TransactionalCatalogRepository(self.store)
        application = CatalogApplication(
            repository,
            IncrementingClock(),
            CatalogPolicy(
                default_catalog_id="000000000000",
                api_page_size=100,
                create_default_database=False,
                partition_expressions=PartitionExpressionPolicy(
                    max_length=2048,
                    max_tokens=512,
                    supported_key_types=(
                        "string",
                        "date",
                        "timestamp",
                        "int",
                        "bigint",
                        "long",
                        "tinyint",
                        "smallint",
                        "decimal",
                    ),
                ),
            ),
        )
        endpoint = AwsJsonRpcEndpoint(
            AwsServiceModel("glue"),
            GlueAwsAdapter(application, "000000000000").dispatcher(),
            default_region="us-east-1",
            account_id="000000000000",
        )
        app = FastAPI()

        @app.post("/")
        async def aws(request: Request):
            return await endpoint(request)

        self._client = TestClient(app)

    def close(self) -> None:
        self._client.close()

    def call(self, operation: str, payload: dict):
        return self._client.post(
            "/",
            headers={"X-Amz-Target": f"AWSGlue.{operation}"},
            json=payload,
        )

    def require_success(self, operation: str, payload: dict) -> dict:
        response = self.call(operation, payload)
        assert response.status_code == 200, response.text
        return response.json()

    def arrange(self, name: str) -> None:
        if name == "empty":
            return
        self.require_success("CreateDatabase", {"DatabaseInput": {"Name": "source"}})
        if name == "database":
            return
        if name == "two_databases":
            self.require_success("CreateDatabase", {"DatabaseInput": {"Name": "target"}})
            return
        self.require_success(
            "CreateTable",
            {
                "DatabaseName": "source",
                "TableInput": {
                    "Name": "events",
                    "StorageDescriptor": {"Columns": []},
                    "PartitionKeys": [{"Name": "day", "Type": "string"}],
                },
            },
        )
        if name == "table":
            return
        if name == "two_tables":
            self.require_success(
                "CreateTable",
                {
                    "DatabaseName": "source",
                    "TableInput": {"Name": "target", "StorageDescriptor": {"Columns": []}},
                },
            )
            return
        raise AssertionError(f"Unknown test arrangement {name}")

    def durable_state(self) -> CatalogState:
        return self.store.load()


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
            "TableInput": {"Name": "events", "Parameters": {"revision": "one"}},
            "VersionId": "0",
        },
    )
    catalog.require_success(
        "UpdateTable",
        {
            "DatabaseName": "warehouse",
            "Name": "events",
            "TableInput": {"Name": "renamed", "Parameters": {"revision": "two"}},
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
    store = ToggleFailureStore()
    catalog = GlueCatalogHarness(store)
    try:
        catalog.arrange("table")
        before = catalog.durable_state()
        store.fail = True

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
