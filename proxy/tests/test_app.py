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


def test_console_and_component_diagnostics_are_registry_driven() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/_mystack/diagnostics/threads"
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(200, json={"service": "emr", "thread_count": 2})

    route = ServiceRoute(
        name="emr",
        backend_url="http://emr:8080",
        target_prefixes=("ElasticMapReduce",),
        signing_names=("elasticmapreduce",),
        host_prefixes=("emr",),
    )
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(
        create_app(
            settings((route,)),
            client=async_client,
            diagnostics_settings=_DIAGNOSTICS,
        )
    ) as client:
        assert client.get("/_mystack/components").json() == {"components": ["proxy", "emr"]}
        assert "Mystack Console" in client.get("/_mystack/console").text
        response = client.get(
            "/_mystack/components/emr/diagnostics/threads",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    assert response.json() == {"service": "emr", "thread_count": 2}


def test_resource_and_log_management_are_forwarded_without_domain_coupling() -> None:
    observed: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append((request.url.path, request.url.query.decode()))
        if request.url.path.endswith("resources"):
            return httpx.Response(200, json={"service": "emr", "resources": {"clusters": []}})
        return httpx.Response(200, json={"service": "emr", "stdout": "ok", "stderr": ""})

    route = ServiceRoute(
        name="emr",
        backend_url="http://emr:8080",
        target_prefixes=("ElasticMapReduce",),
        signing_names=("elasticmapreduce",),
        host_prefixes=("emr",),
    )
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(
        create_app(
            settings((route,)),
            client=async_client,
            diagnostics_settings=_DIAGNOSTICS,
        )
    ) as client:
        resources = client.get("/_mystack/components/emr/resources")
        logs = client.get(
            "/_mystack/components/emr/logs",
            params={"cluster_id": "j-1", "step_id": "s-1"},
        )

    assert resources.json()["service"] == "emr"
    assert logs.json()["stdout"] == "ok"
    assert observed == [
        ("/_mystack/management/resources", ""),
        ("/_mystack/management/logs", "cluster_id=j-1&step_id=s-1"),
    ]
