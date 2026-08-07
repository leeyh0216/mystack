"""Byte-preserving Proxy HTTP boundary tests.

Reference: https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from mystack_aws_protocol import DiagnosticsSettings
from mystack_proxy.app import create_app
from mystack_proxy.config import ProxySettings, ServiceRoute

_DIAGNOSTICS = DiagnosticsSettings(enabled=True, management_token=None, stack_limit=20)


def settings(routes: tuple[ServiceRoute, ...] = ()) -> ProxySettings:
    return ProxySettings(
        fallback_url="http://localstack:4566",
        routes=routes,
        request_timeout_seconds=30,
        listen_host="127.0.0.1",
        listen_port=8080,
        config_source="test",
        config_fingerprint="test-fingerprint",
    )


def test_forwards_original_body_to_glue_backend() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["body"] = request.content
        observed["target"] = request.headers["x-amz-target"]
        return httpx.Response(
            200,
            content=b'{"Job":{"Name":"demo"}}',
            headers={"content-type": "application/x-amz-json-1.1"},
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    proxy_settings = settings(
        (
            ServiceRoute(
                name="glue",
                backend_url="http://glue:8080",
                target_prefixes=("AWSGlue",),
                signing_names=("glue",),
                host_prefixes=("glue",),
            ),
        )
    )
    with TestClient(
        create_app(proxy_settings, client=async_client, diagnostics_settings=_DIAGNOSTICS)
    ) as client:
        response = client.post(
            "/",
            headers={"X-Amz-Target": "AWSGlue.GetJob"},
            content=b'{ "JobName" : "demo" }',
        )

    assert response.status_code == 200
    assert observed == {
        "url": "http://glue:8080/",
        "body": b'{ "JobName" : "demo" }',
        "target": "AWSGlue.GetJob",
    }


def test_forwards_path_query_and_unknown_service_to_localstack() -> None:
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        return httpx.Response(204)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(
        create_app(settings(), client=async_client, diagnostics_settings=_DIAGNOSTICS)
    ) as client:
        response = client.put("/bucket/key?versionId=1", content=b"data")

    assert response.status_code == 204
    assert observed["url"] == "http://localstack:4566/bucket/key?versionId=1"
