"""EMR management read-model boundary contracts.

Reference: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mystack.emr.adapters.inbound.management import EmrManagementAdapter


def _adapter(application: object) -> EmrManagementAdapter:
    return EmrManagementAdapter(
        application,  # type: ignore[arg-type]
        work_root=Path("/tmp/mystack-test-emr"),
        output_tail_bytes=1024,
        implemented_operations=frozenset({"RunJobFlow"}),
        model_operation_count=50,
        config_fingerprint="test-fingerprint",
        default_release_label="emr-test",
        release_profiles={
            "emr-test": {
                "runtime_profile": "spark-test",
                "aws_spark_version": "3.5.x-test",
            }
        },
    )


@pytest.mark.asyncio
async def test_resources_expose_configured_release_choices() -> None:
    application = SimpleNamespace(list_clusters=AsyncMock(return_value=([], None)))

    document = await _adapter(application).resources()

    assert document["emulator"]["default_release_label"] == "emr-test"
    assert document["emulator"]["release_profiles"]["emr-test"]["runtime_profile"] == ("spark-test")


@pytest.mark.asyncio
async def test_resource_query_failure_is_logged_with_fix_hint(caplog) -> None:
    application = SimpleNamespace(
        list_clusters=AsyncMock(side_effect=RuntimeError("repository unavailable"))
    )

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        await _adapter(application).resources()

    record = next(record for record in caplog.records if record.msg.endswith("resources.failed"))
    assert record.mystack_fields["fix_hint"]
