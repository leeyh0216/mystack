"""EMR service-owned compiled React UI delivery contracts.

References:
- https://www.starlette.io/staticfiles/
- https://developer.mozilla.org/en-US/docs/Web/API/History_API
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.contract
def test_emr_emulator_serves_its_compiled_react_ui_and_runtime_config(
    emr_server,
    test_timeout: float,
) -> None:
    endpoint_url, _ = emr_server

    config = httpx.get(f"{endpoint_url}/_mystack/ui/emr/config", timeout=test_timeout)
    index = httpx.get(f"{endpoint_url}/_mystack/ui/emr/", timeout=test_timeout)
    deep_link = httpx.get(
        f"{endpoint_url}/_mystack/ui/emr/clusters/j-DEEP/steps/s-DEEP/logs",
        headers={"Accept": "text/html"},
        timeout=test_timeout,
    )

    assert config.status_code == 200
    assert config.json()["log_buffer_bytes"] == 1_048_576
    assert index.status_code == 200
    assert '<div id="root"></div>' in index.text
    assert deep_link.status_code == 200
    assert '<div id="root"></div>' in deep_link.text
    assert "Management token" not in index.text
