"""Deterministic Glue AWS JSON boundary harness for catalog error contracts.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
- https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

from __future__ import annotations

import copy

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack.aws_protocol import AwsJsonRpcEndpoint, AwsServiceModel
from mystack.glue.adapters.inbound.aws import GlueAwsAdapter
from mystack.glue.adapters.outbound import CatalogStateStore, TransactionalCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.policies import GlueFaultInjectionPolicy
from mystack.glue.domain import CatalogState


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
        self.save_attempts = 0
        self.fail_on_attempt: int | None = None

    def load(self) -> CatalogState:
        return copy.deepcopy(self._committed)

    async def save(self, candidate: CatalogState) -> None:
        self.save_attempts += 1
        if self.fail or self.save_attempts == self.fail_on_attempt:
            raise OSError("deterministic test persistence failure")
        self._committed = copy.deepcopy(candidate)


class GlueCatalogHarness:
    """Compose real application/repository objects behind the shared wire controller."""

    def __init__(
        self,
        store: ToggleFailureStore | None = None,
        fault_injection: GlueFaultInjectionPolicy | None = None,
    ) -> None:
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

    def durable_state(self) -> CatalogState:
        return self.store.load()
