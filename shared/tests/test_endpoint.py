from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack_aws_protocol import AwsJsonRpcEndpoint, AwsServiceError, AwsServiceModel
from mystack_aws_protocol.dispatcher import OperationDispatcher


def app_for(dispatcher: OperationDispatcher) -> FastAPI:
    app = FastAPI()
    endpoint = AwsJsonRpcEndpoint(AwsServiceModel("glue"), dispatcher)

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
