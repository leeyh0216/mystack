"""Management diagnostic contracts.

Reference: https://docs.python.org/3/library/sys.html#sys._current_frames
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mystack.aws_protocol import DiagnosticsSettings, create_diagnostics_router


def test_thread_diagnostics_expose_stack_without_locals() -> None:
    app = FastAPI()
    settings = DiagnosticsSettings(enabled=True, stack_limit=20)
    app.include_router(create_diagnostics_router("test-service", settings))

    response = TestClient(app).get("/_mystack/diagnostics/threads")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "test-service"
    assert payload["thread_count"] >= 1
    assert all("stack" in thread for thread in payload["threads"])
    assert all("locals" not in thread for thread in payload["threads"])


def test_disabled_diagnostics_return_not_found_without_authentication_behavior() -> None:
    app = FastAPI()
    settings = DiagnosticsSettings(enabled=False, stack_limit=20)
    app.include_router(create_diagnostics_router("test-service", settings))
    client = TestClient(app)

    response = client.get(
        "/_mystack/diagnostics/tasks",
        headers={"Authorization": "Bearer ignored-by-design"},
    )

    assert response.status_code == 404
