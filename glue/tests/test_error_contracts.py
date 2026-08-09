"""Deterministic Glue error-boundary and fault-injection contracts.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
- https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mystack.aws_protocol import (
    AwsJsonRpcEndpoint,
    AwsServiceModel,
    ConfigurationError,
    load_configuration,
)
from mystack.glue.adapters.inbound.aws import GlueAwsAdapter
from mystack.glue.application.policies import GlueFaultInjectionPolicy, GlueFaultRule
from mystack.glue.config import GlueSettings


class GuardedApplication:
    def __init__(self, failure: Exception | None = None) -> None:
        self.called = False
        self.failure = failure

    async def get_database(self, catalog_id: str, name: str):
        del catalog_id, name
        self.called = True
        if self.failure is not None:
            raise self.failure
        raise AssertionError("The test expects the error boundary to stop this handler")

    async def create_database(self, catalog_id: str, definition: dict):
        del catalog_id, definition
        self.called = True
        raise AssertionError("The test expects the error boundary to stop this handler")


def test_protocol_validation_precedes_configured_fault_and_mutation(caplog) -> None:
    application = GuardedApplication()
    policy = GlueFaultInjectionPolicy(
        enabled=True,
        rules=(
            GlueFaultRule(
                "timeout-get-database",
                "GetDatabase",
                "OperationTimeoutException",
                "configured timeout",
            ),
            GlueFaultRule(
                "internal-create-database",
                "CreateDatabase",
                "InternalServiceException",
                "configured internal failure",
            ),
        ),
    )
    client = TestClient(_app(application, policy))

    invalid = client.post(
        "/",
        headers={"X-Amz-Target": "AWSGlue.GetDatabase"},
        json={},
    )
    with caplog.at_level(logging.INFO):
        timeout = client.post(
            "/",
            headers={"X-Amz-Target": "AWSGlue.GetDatabase"},
            json={"Name": "analytics"},
        )
        internal = client.post(
            "/",
            headers={"X-Amz-Target": "AWSGlue.CreateDatabase"},
            json={"DatabaseInput": {"Name": "analytics"}},
        )

    assert invalid.status_code == 400
    assert invalid.json()["__type"] == "InvalidInputException"
    assert timeout.status_code == 400
    assert timeout.json() == {
        "__type": "OperationTimeoutException",
        "Message": "configured timeout",
    }
    assert internal.status_code == 500
    assert internal.json()["__type"] == "InternalServiceException"
    assert application.called is False
    decisions = [
        getattr(record, "mystack_fields", {})
        for record in caplog.records
        if record.getMessage() == "glue.error.decision"
    ]
    assert {value["condition_id"] for value in decisions} == {
        "fault.operation_timeout",
        "fault.internal_service",
    }
    assert {value["mutation_guarantee"] for value in decisions} == {"handler_not_called"}


def test_adapter_mapping_failure_is_sanitized_system_error(caplog) -> None:
    secret = "payload-derived-value-must-not-be-logged"
    application = GuardedApplication(KeyError(secret))
    client = TestClient(_app(application, GlueFaultInjectionPolicy.disabled()))

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/",
            headers={"X-Amz-Target": "AWSGlue.GetDatabase"},
            json={"Name": "analytics"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "__type": "InternalServiceException",
        "Message": "An internal Glue request mapping error occurred.",
    }
    emitted = json.dumps(
        [
            {
                "event": record.getMessage(),
                "fields": getattr(record, "mystack_fields", {}),
            }
            for record in caplog.records
        ],
        default=str,
    )
    assert secret not in emitted
    decision = next(
        value
        for value in (getattr(record, "mystack_fields", {}) for record in caplog.records)
        if value.get("condition_id") == "adapter.mapping_failure"
    )
    assert decision["failure_type"] == "KeyError"
    assert decision["category"] == "system"
    assert decision["mutation_guarantee"] == "candidate_not_committed"


@pytest.mark.parametrize(
    ("rule", "message"),
    (
        (
            GlueFaultRule("auth", "GetDatabase", "AccessDeniedException", "forbidden"),
            "forbidden error",
        ),
        (
            GlueFaultRule("unknown", "StartCrawler", "InternalServiceException", "unknown"),
            "unsupported operation",
        ),
        (
            GlueFaultRule("", "GetDatabase", "InternalServiceException", "internal"),
            "id cannot be empty",
        ),
        (
            GlueFaultRule("empty-message", "GetDatabase", "InternalServiceException", ""),
            "response message cannot be empty",
        ),
    ),
)
def test_fault_injection_rejects_out_of_scope_or_unsupported_rules(
    rule: GlueFaultRule,
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        GlueAwsAdapter(
            GuardedApplication(),  # type: ignore[arg-type]
            "000000000000",
            GlueFaultInjectionPolicy(enabled=True, rules=(rule,)),
        )


def test_fault_policy_can_be_supplied_by_typed_docker_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__GLUE__FAULT_INJECTION__ENABLED", "true")
    monkeypatch.setenv(
        "MYSTACK__GLUE__FAULT_INJECTION__RULES",
        "[{id: timeout-table, operation: GetTable, "
        "error_code: OperationTimeoutException, message: injected}]",
    )

    settings = GlueSettings.from_configuration(load_configuration("config/runtime/mystack.yaml"))

    assert settings.fault_injection == GlueFaultInjectionPolicy(
        enabled=True,
        rules=(
            GlueFaultRule(
                "timeout-table",
                "GetTable",
                "OperationTimeoutException",
                "injected",
            ),
        ),
    )


def _app(application: GuardedApplication, policy: GlueFaultInjectionPolicy) -> FastAPI:
    app = FastAPI()
    model = AwsServiceModel("glue")
    endpoint = AwsJsonRpcEndpoint(
        model,
        GlueAwsAdapter(application, "000000000000", policy).dispatcher(),  # type: ignore[arg-type]
        default_region="us-east-1",
        account_id="000000000000",
    )

    @app.post("/")
    async def aws(request: Request):
        return await endpoint(request)

    return app
