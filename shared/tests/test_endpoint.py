from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack_aws_protocol import AwsJsonRpcEndpoint, AwsServiceError, AwsServiceModel
from mystack_aws_protocol.dispatcher import OperationDispatcher


def app_for(dispatcher: OperationDispatcher) -> FastAPI:
    app = FastAPI()
    endpoint = AwsJsonRpcEndpoint(
        AwsServiceModel("glue"),
        dispatcher,
        default_region="test-region-1",
        account_id="000000000000",
    )

    @app.post("/")
    async def aws(request: Request):
        return await endpoint(request)

    return app


def test_dispatches_a_valid_aws_json_request() -> None:
    seen: dict[str, Any] = {}

    async def get_database(payload, context):
        seen.update(payload)
        assert context.operation == "GetDatabase"
        assert context.region == "ap-northeast-2"
        return {"Database": {"Name": payload["Name"]}}

    client = TestClient(app_for(OperationDispatcher({"GetDatabase": get_database})))
    response = client.post(
        "/",
        headers={
            "X-Amz-Target": "AWSGlue.GetDatabase",
            "Content-Type": "application/x-amz-json-1.1",
            "Authorization": (
                "AWS4-HMAC-SHA256 Credential=test/20260808/ap-northeast-2/glue/aws4_request, "
                "SignedHeaders=host;x-amz-date, Signature=0"
            ),
        },
        json={"Name": "analytics"},
    )

    assert response.status_code == 200
    assert response.json() == {"Database": {"Name": "analytics"}}
    assert response.headers["x-amzn-requestid"]
    assert seen == {"Name": "analytics"}


def test_returns_modeled_service_error() -> None:
    async def create_database(payload, context):
        raise AwsServiceError("AlreadyExistsException", "Database already exists")

    client = TestClient(app_for(OperationDispatcher({"CreateDatabase": create_database})))
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AWSGlue.CreateDatabase"},
        json={"DatabaseInput": {"Name": "analytics"}},
    )

    assert response.status_code == 400
    assert response.headers["x-amzn-errortype"] == "AlreadyExistsException"
    assert response.json()["__type"] == "AlreadyExistsException"


def test_rejects_payload_that_violates_the_official_shape() -> None:
    client = TestClient(app_for(OperationDispatcher()))
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AWSGlue.GetDatabase"},
        json={},
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidInputException"
    assert "Name" in response.json()["Message"]


def test_rejects_official_enum_and_pattern_constraints() -> None:
    client = TestClient(app_for(OperationDispatcher()))
    enum_response = client.post(
        "/",
        headers={"X-Amz-Target": "AWSGlue.CreateDatabase"},
        json={
            "DatabaseInput": {
                "Name": "analytics",
                "CreateTableDefaultPermissions": [
                    {"Principal": {"DataLakePrincipalIdentifier": "test"}, "Permissions": ["NOPE"]}
                ],
            }
        },
    )
    pattern_response = client.post(
        "/",
        headers={"X-Amz-Target": "AWSGlue.CreateTable"},
        json={
            "DatabaseName": "analytics",
            "TableInput": {
                "Name": "events",
                "StorageDescriptor": {"SchemaReference": {"SchemaVersionId": "Z" * 36}},
            },
        },
    )

    assert enum_response.status_code == 400
    assert "must be one of" in enum_response.json()["Message"]
    assert pattern_response.status_code == 400
    assert "must satisfy modeled pattern" in pattern_response.json()["Message"]


def test_validation_logs_never_include_payload_values(caplog) -> None:
    secret = "never-log-this-payload-value"
    client = TestClient(app_for(OperationDispatcher()))
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/",
            headers={"X-Amz-Target": "AWSGlue.GetDatabase"},
            json={"Name": {"secret": secret}},
        )

    assert response.status_code == 400
    emitted = json.dumps(
        [
            {
                "message": record.getMessage(),
                "fields": getattr(record, "mystack_fields", {}),
            }
            for record in caplog.records
        ],
        default=str,
    )
    assert secret not in emitted
