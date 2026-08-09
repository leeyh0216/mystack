"""Deterministic Glue AWS JSON boundary harness for catalog error contracts.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
- https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack.aws_protocol import AwsJsonRpcEndpoint, AwsServiceModel
from mystack.glue.adapters.inbound.aws import GlueAwsAdapter
from mystack.glue.adapters.outbound import SqliteCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.policies import GlueFaultInjectionPolicy
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)


class InMemoryIcebergMetadataStore:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    async def read(self, location: str) -> dict:
        if location not in self.documents:
            raise OSError("deterministic missing metadata")
        return copy.deepcopy(self.documents[location])

    async def write(self, location: str, document: dict) -> None:
        self.documents[location] = copy.deepcopy(document)

    async def delete(self, location: str) -> None:
        self.documents.pop(location, None)


class IncrementingIdentifierGenerator:
    def __init__(self) -> None:
        self._value = 0

    def new(self) -> str:
        self._value += 1
        return f"00000000-0000-0000-0000-{self._value:012d}"


class IncrementingClock:
    def __init__(self) -> None:
        self._value = 0.0

    def now(self) -> float:
        self._value += 1.0
        return self._value


class ToggleCommitFailpoint:
    """Test-only SQLite transaction hook; no catalog data is stored in memory."""

    def __init__(self) -> None:
        self.fail = False
        self.save_attempts = 0
        self.fail_on_attempt: int | None = None

    async def before_commit(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
        mutated: bool,
    ) -> None:
        del operation, resource_key, mutated
        self.save_attempts += 1
        if self.fail or self.save_attempts == self.fail_on_attempt:
            raise OSError("deterministic test persistence failure")


@dataclass(frozen=True, slots=True)
class CatalogDurableView:
    """SQLite-derived test inspection only; it is not a production aggregate or store."""

    databases: dict[tuple[str, str], tuple[str, float]]
    tables: dict[tuple[str, str, str], tuple[str, str, float, float]]
    partitions: dict[tuple[str, str, str, tuple[str, ...]], tuple[str, float, float]]
    optimizers: dict[tuple[str, str, str, str], tuple[str, int, float | None]]


class GlueCatalogHarness:
    """Compose real application/repository objects behind the shared wire controller."""

    def __init__(
        self,
        failpoint: ToggleCommitFailpoint | None = None,
        fault_injection: GlueFaultInjectionPolicy | None = None,
    ) -> None:
        self.failpoint = failpoint or ToggleCommitFailpoint()
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="mystack-glue-harness-")
        database_file = Path(self._temporary_directory.name) / "catalog.sqlite3"
        self.metadata_store = InMemoryIcebergMetadataStore()
        settings = SQLiteRuntimeSettings(
            database_file=database_file,
            driver=SQLiteDriverSettings(
                module="sqlite3",
                expected_version="3.53.4",
                minimum_wal_version="3.51.3",
                manifest_file=database_file.with_name("unused-runtime-manifest.json"),
            ),
            journal_mode="rollback",
            synchronous="full",
            busy_timeout_milliseconds=250,
            retry_limit=0,
            checkpoint=SQLiteCheckpointSettings(mode="passive", auto_checkpoint_pages=1000),
        )
        self._database_file = database_file
        catalog = SqliteCatalogRepository(settings, transaction_hook=self.failpoint)
        application = CatalogApplication(
            catalog,
            catalog,
            catalog,
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
            iceberg_metadata_store=self.metadata_store,
            identifier_generator=IncrementingIdentifierGenerator(),
        )
        endpoint = AwsJsonRpcEndpoint(
            AwsServiceModel("glue"),
            GlueAwsAdapter(
                application,
                "000000000000",
                fault_injection,
            ).dispatcher(),
            default_region="us-east-1",
            account_id="000000000000",
        )
        app = FastAPI()

        @app.post("/")
        async def aws(request: Request):
            return await endpoint(request)

        self._client = TestClient(app)

    def close(self) -> None:
        try:
            self._client.close()
        finally:
            self._temporary_directory.cleanup()

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

    def arrange(self, arrangement: str) -> None:
        if arrangement == "empty":
            return
        self.require_success("CreateDatabase", {"DatabaseInput": {"Name": "source"}})
        if arrangement == "database":
            return
        if arrangement == "two_databases":
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
        if arrangement == "table":
            return
        if arrangement == "two_tables":
            self.require_success(
                "CreateTable",
                {
                    "DatabaseName": "source",
                    "TableInput": {"Name": "target", "StorageDescriptor": {"Columns": []}},
                },
            )
            return
        raise AssertionError(f"Unknown test arrangement {arrangement}")

    def durable_state(self) -> CatalogDurableView:
        """Inspect committed normalized rows directly for wire-level error assertions."""
        if not self._database_file.exists():
            return CatalogDurableView({}, {}, {}, {})
        connection = sqlite3.connect(self._database_file)
        try:
            schema = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'catalog_databases'"
            ).fetchone()
            if schema is None:
                return CatalogDurableView({}, {}, {}, {})
            databases = {
                (str(catalog_id), str(name)): (str(definition), float(create_time))
                for catalog_id, name, definition, create_time in connection.execute(
                    "SELECT catalog_id, name, definition_json, create_time FROM catalog_databases"
                )
            }
            tables = {
                (str(catalog_id), str(database_name), str(table_name)): (
                    str(definition),
                    str(version_id),
                    float(create_time),
                    float(update_time),
                )
                for (
                    catalog_id,
                    database_name,
                    table_name,
                    definition,
                    version_id,
                    create_time,
                    update_time,
                ) in connection.execute(
                    "SELECT d.catalog_id, d.name, t.name, t.definition_json, t.version_id, "
                    "t.create_time, t.update_time FROM catalog_tables AS t "
                    "JOIN catalog_databases AS d ON d.database_id = t.database_id"
                )
            }
            partitions = {
                (str(catalog_id), str(database_name), str(table_name), tuple(json.loads(values))): (
                    str(definition),
                    float(create_time),
                    float(update_time),
                )
                for (
                    catalog_id,
                    database_name,
                    table_name,
                    values,
                    definition,
                    create_time,
                    update_time,
                ) in connection.execute(
                    "SELECT d.catalog_id, d.name, t.name, p.values_json, p.definition_json, "
                    "p.creation_time, p.update_time FROM catalog_partitions AS p "
                    "JOIN catalog_tables AS t ON t.table_id = p.table_id "
                    "JOIN catalog_databases AS d ON d.database_id = t.database_id"
                )
            }
            optimizers = {
                (str(catalog_id), str(database_name), str(table_name), str(optimizer_type)): (
                    str(configuration),
                    int(revision),
                    None if next_run is None else float(next_run),
                )
                for (
                    catalog_id,
                    database_name,
                    table_name,
                    optimizer_type,
                    configuration,
                    revision,
                    next_run,
                ) in connection.execute(
                    "SELECT d.catalog_id, d.name, t.name, o.optimizer_type, o.configuration_json, "
                    "o.revision, o.next_run_time FROM catalog_table_optimizers AS o "
                    "JOIN catalog_tables AS t ON t.table_id = o.table_id "
                    "JOIN catalog_databases AS d ON d.database_id = t.database_id"
                )
            }
        finally:
            connection.close()
        return CatalogDurableView(databases, tables, partitions, optimizers)
