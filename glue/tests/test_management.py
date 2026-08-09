"""Glue management read-model boundary contracts.

Reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

import copy
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from mystack.aws_protocol import LoadedConfiguration, load_configuration
from mystack.glue.adapters.inbound.management import GlueManagementAdapter
from mystack.glue.app import create_app


@pytest.mark.asyncio
async def test_resource_query_failure_is_logged_with_fix_hint(caplog) -> None:
    application = SimpleNamespace(
        get_databases=AsyncMock(side_effect=RuntimeError("repository unavailable"))
    )
    adapter = GlueManagementAdapter(
        application,  # type: ignore[arg-type]
        catalog_id="000000000000",
        api_page_size=10,
        implemented_operations=frozenset({"GetDatabases"}),
        model_operation_count=50,
        runtime_profile="glue-test",
        config_fingerprint="test-fingerprint",
    )

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        await adapter.resources()

    record = next(record for record in caplog.records if record.msg.endswith("resources.failed"))
    assert record.mystack_fields["fix_hint"]


def test_glue_emulator_serves_its_compiled_react_ui_and_runtime_config(tmp_path) -> None:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path)
    document["glue"]["sqlite"]["journal_mode"] = "rollback"
    document["glue"]["sqlite"]["driver"]["module"] = "sqlite3"
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"test-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )

    with TestClient(create_app(configuration=configured)) as client:
        config = client.get("/_mystack/ui/glue/config")
        index = client.get("/_mystack/ui/glue/")
        deep_link = client.get(
            "/_mystack/ui/glue/databases/default/tables/events/partitions",
            headers={"Accept": "text/html"},
        )

    assert config.status_code == 200
    assert config.json()["refresh_interval_seconds"] == 2
    assert index.status_code == 200
    assert '<div id="root"></div>' in index.text
    assert deep_link.status_code == 200
    assert '<div id="root"></div>' in deep_link.text
    assert "Management token" not in index.text
