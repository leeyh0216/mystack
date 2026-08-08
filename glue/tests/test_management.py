"""Glue management read-model boundary contracts.

Reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mystack.glue.adapters.inbound.management import GlueManagementAdapter


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
