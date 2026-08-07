"""Management diagnostic contracts.

Reference: https://docs.python.org/3/library/sys.html#sys._current_frames
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mystack_aws_protocol import DiagnosticsSettings, create_diagnostics_router


def test_thread_diagnostics_expose_stack_without_locals() -> None:
    app = FastAPI()
    settings = DiagnosticsSettings(enabled=True, management_token=None, stack_limit=20)
    app.include_router(create_diagnostics_router("test-service", settings))

    response = TestClient(app).get("/_mystack/diagnostics/threads")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "test-service"
    assert payload["thread_count"] >= 1
    assert all("stack" in thread for thread in payload["threads"])
    assert all("locals" not in thread for thread in payload["threads"])


def test_diagnostics_require_configured_bearer_token() -> None:
    app = FastAPI()
    settings = DiagnosticsSettings(
        enabled=True,
        management_token="management-secret",
        stack_limit=20,
    )
    app.include_router(create_diagnostics_router("test-service", settings))
    client = TestClient(app)

    denied = client.get("/_mystack/diagnostics/tasks")
    allowed = client.get(
        "/_mystack/diagnostics/tasks",
        headers={"Authorization": "Bearer management-secret"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["task_count"] >= 1
