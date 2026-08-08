"""EMR management read-model boundary contracts.

Reference: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from mystack.aws_protocol import ManagementUiSettings
from mystack.emr.adapters.inbound.log_stream import EmrLogEventStream
from mystack.emr.adapters.inbound.management import EmrManagementAdapter
from mystack.emr.domain.errors import ClusterNotFoundError


def _adapter(
    application: object,
    *,
    work_root: Path = Path("/tmp/mystack-test-emr"),
    journal: object | None = None,
) -> EmrManagementAdapter:
    return EmrManagementAdapter(
        application,  # type: ignore[arg-type]
        work_root=work_root,
        output_tail_bytes=1024,
        live_chunk_bytes=256,
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
        execution_journal=journal,  # type: ignore[arg-type]
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


@pytest.mark.asyncio
async def test_log_chunks_are_bounded_and_recovered_records_remain_explorable(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "j-OLD" / "s-OLD"
    work_dir.mkdir(parents=True)
    (work_dir / "stdout.log").write_text("abcdefgh", encoding="utf-8")
    (work_dir / "stderr.log").write_text("error", encoding="utf-8")
    (work_dir / "log-publication.json").write_text(
        '{"schema_version":1,"status":"published"}',
        encoding="utf-8",
    )
    record = SimpleNamespace(
        cluster_id="j-OLD",
        cluster_name="recovered cluster",
        release_label="emr-test",
        step_id="s-OLD",
        step_name="recovered step",
        log_uri="s3://logs/emr/",
        state="interrupted",
        started_at_epoch_seconds=1.0,
        completed_at_epoch_seconds=2.0,
        exit_code=None,
        reason="emulator restarted",
        work_dir=work_dir,
    )
    journal = SimpleNamespace(
        records=AsyncMock(return_value=(record,)),
        find=AsyncMock(return_value=record),
    )
    application = SimpleNamespace(
        list_clusters=AsyncMock(return_value=([], None)),
        describe_cluster=AsyncMock(side_effect=ClusterNotFoundError("j-OLD")),
    )
    adapter = _adapter(application, work_root=tmp_path, journal=journal)
    adapter._live_chunk_bytes = 4

    resources = await adapter.resources()
    first = await adapter.log_chunk("j-OLD", "s-OLD", stdout_offset=0, stderr_offset=0)
    second = await adapter.log_chunk(
        "j-OLD",
        "s-OLD",
        stdout_offset=first["stdout_next_offset"],
        stderr_offset=first["stderr_next_offset"],
    )

    assert resources["counts"]["recovered_clusters"] == 1
    assert resources["resources"]["clusters"][0]["recovered"] is True
    assert first["stdout"] == "abcd"
    assert first["complete"] is False
    assert second["stdout"] == "efgh"
    assert second["complete"] is True


@pytest.mark.asyncio
async def test_log_resource_ids_reject_path_traversal() -> None:
    application = SimpleNamespace()

    with pytest.raises(ValueError, match="must contain"):
        await _adapter(application).log_chunk(
            "../j-escape",
            "s-1",
            stdout_offset=0,
            stderr_offset=0,
        )


@pytest.mark.asyncio
async def test_service_owned_log_stream_resumes_with_bounded_offsets() -> None:
    logs = SimpleNamespace(
        log_chunk=AsyncMock(
            return_value={
                "stdout": "next line\n",
                "stderr": "",
                "stdout_next_offset": 20,
                "stderr_next_offset": 7,
                "step_state": "COMPLETED",
                "log_publication": {"status": "published"},
                "complete": True,
            }
        )
    )

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/_mystack/ui/emr/log-stream",
            "headers": [(b"last-event-id", b"12:7")],
            "client": ("127.0.0.1", 1234),
        },
        receive,
    )
    stream = EmrLogEventStream(
        logs,
        ManagementUiSettings(
            refresh_interval_seconds=2,
            log_stream_poll_interval_seconds=0.1,
            log_stream_timeout_seconds=10,
            log_buffer_bytes=4096,
        ),
    )

    content = b"".join(
        [
            chunk
            async for chunk in stream.events(
                request,
                cluster_id="j-1",
                step_id="s-1",
                stdout_offset=0,
                stderr_offset=0,
            )
        ]
    )

    logs.log_chunk.assert_awaited_once_with(
        "j-1",
        "s-1",
        stdout_offset=12,
        stderr_offset=7,
    )
    assert b"event: logs" in content
    assert b"id: 20:7" in content
