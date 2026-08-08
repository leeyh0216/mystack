"""Proxy runtime ownership and failure-path contracts.

HTTPX client lifecycle reference:
https://www.python-httpx.org/advanced/clients/#opening-and-closing-clients
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Never
from unittest.mock import AsyncMock

import httpx
import pytest
from mystack.proxy.config import ProxySettings, ServiceRoute
from mystack.proxy.runtime import ProxyRuntime, RuntimeState


def settings() -> ProxySettings:
    """Build the minimal runtime settings without coupling one test module to another."""

    return ProxySettings(
        fallback_url="http://localstack:4566",
        routes=(),
        request_timeout_seconds=30,
        listen_host="127.0.0.1",
        listen_port=8080,
        config_source="test",
        config_fingerprint="test-fingerprint",
    )


@pytest.mark.asyncio
async def test_runtime_closes_the_shared_client_exactly_once() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(204)))
    close = AsyncMock(wraps=client.aclose)
    client.aclose = close
    runtime = ProxyRuntime(settings(), client=client)

    await runtime.start()
    await runtime.aclose()
    await runtime.aclose()

    assert close.await_count == 1
    assert runtime.state is RuntimeState.CLOSED


@pytest.mark.asyncio
async def test_startup_failure_closes_a_created_client_exactly_once() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(204)))
    close = AsyncMock(wraps=client.aclose)
    client.aclose = close

    def fail_detector(_routes: Sequence[ServiceRoute]) -> Never:
        raise RuntimeError("detector construction failed")

    runtime = ProxyRuntime(
        settings(),
        client=client,
        detector_factory=fail_detector,
    )

    with pytest.raises(RuntimeError, match="detector construction failed"):
        await runtime.start()
    await runtime.aclose()

    assert close.await_count == 1
    assert runtime.state is RuntimeState.CLOSED


@pytest.mark.asyncio
async def test_runtime_rejects_ambiguous_client_ownership() -> None:
    client = httpx.AsyncClient()
    try:
        with pytest.raises(ValueError, match="mutually exclusive"):
            ProxyRuntime(settings(), client=client, client_factory=lambda: client)
    finally:
        await client.aclose()
