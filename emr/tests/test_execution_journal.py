"""Durable EMR Step recovery contracts.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
- https://docs.python.org/3/library/os.html#os.replace
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from mystack.emr.adapters.outbound.journal import StepExecutionJournal
from mystack.emr.adapters.outbound.logs import StepLogPublicationRequest
from mystack.emr.application.ports import RuntimeResult


class _Publisher:
    def __init__(self) -> None:
        self.requests: list[StepLogPublicationRequest] = []

    async def publish(self, request: StepLogPublicationRequest) -> None:
        self.requests.append(request)
        (request.work_dir / "log-publication.json").write_text(
            json.dumps({"schema_version": 1, "status": "published"}),
            encoding="utf-8",
        )


def _cluster() -> SimpleNamespace:
    return SimpleNamespace(
        id="j-RECOVER",
        name="durable-cluster",
        release_label="emr-7.5.0",
        log_uri="s3://logs/emr/",
    )


def _step() -> SimpleNamespace:
    return SimpleNamespace(id="s-RECOVER", name="durable-step", state="RUNNING")


@pytest.mark.asyncio
async def test_restart_marks_running_step_interrupted_and_republishes_logs(
    tmp_path: Path,
) -> None:
    publisher = _Publisher()
    journal = StepExecutionJournal(
        tmp_path,
        publisher,
        SimpleNamespace(retention_seconds=3600),
    )
    work_dir = tmp_path / "j-RECOVER" / "s-RECOVER"
    await journal.begin(_cluster(), _step(), work_dir)  # type: ignore[arg-type]
    (work_dir / "stdout.log").write_text("survived restart\n", encoding="utf-8")

    recovered = await journal.recover()

    assert len(recovered) == 1
    assert recovered[0].state == "interrupted"
    assert recovered[0].process_started is True
    assert publisher.requests[0].stdout_file == work_dir / "stdout.log"
    persisted = json.loads((work_dir / "execution-journal.json").read_text())
    assert persisted["state"] == "interrupted"
    assert persisted["reason"] == "EMR emulator restarted while the Step was running"


@pytest.mark.asyncio
async def test_terminal_result_is_journaled_before_publication(tmp_path: Path) -> None:
    publisher = _Publisher()
    journal = StepExecutionJournal(
        tmp_path,
        publisher,
        SimpleNamespace(retention_seconds=3600),
    )
    work_dir = tmp_path / "j-RECOVER" / "s-RECOVER"
    await journal.begin(_cluster(), _step(), work_dir)  # type: ignore[arg-type]

    await journal.complete(
        _cluster(),  # type: ignore[arg-type]
        _step(),  # type: ignore[arg-type]
        work_dir,
        RuntimeResult(False, exit_code=17, reason="spark-submit exited with 17"),
        process_started=True,
    )

    persisted = json.loads((work_dir / "execution-journal.json").read_text())
    assert persisted["state"] == "failed"
    assert persisted["exit_code"] == 17
    assert len(publisher.requests) == 1


@pytest.mark.asyncio
async def test_cancel_pending_result_preserves_cancelled_recovery_state(tmp_path: Path) -> None:
    publisher = _Publisher()
    journal = StepExecutionJournal(
        tmp_path,
        publisher,
        SimpleNamespace(retention_seconds=3600),
    )
    work_dir = tmp_path / "j-RECOVER" / "s-RECOVER"
    step = _step()
    step.state = "CANCEL_PENDING"
    await journal.begin(_cluster(), step, work_dir)  # type: ignore[arg-type]

    await journal.complete(
        _cluster(),  # type: ignore[arg-type]
        step,  # type: ignore[arg-type]
        work_dir,
        RuntimeResult(False, exit_code=-15, reason="cancelled"),
        process_started=True,
    )

    persisted = json.loads((work_dir / "execution-journal.json").read_text())
    assert persisted["state"] == "cancelled"
