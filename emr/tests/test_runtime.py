"""Subprocess race regression tests.

References:
- https://docs.python.org/3/library/asyncio-subprocess.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_CancelSteps.html
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from mystack.aws_protocol import load_configuration
from mystack.emr.adapters.outbound import AsyncioTaskScheduler, LocalProcessExecutor
from mystack.emr.config import EmrSettings


@pytest.mark.asyncio
async def test_cancellation_before_process_registration_is_applied(tmp_path: Path) -> None:
    settings = EmrSettings.from_configuration(load_configuration("config/mystack.yaml"))
    executor = LocalProcessExecutor(settings)

    await executor.cancel("j-race", "s-race")
    outcome = await executor.execute(
        cluster_id="j-race",
        operation_id="s-race",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        work_dir=tmp_path,
        timeout_seconds=5,
        environment={},
    )

    assert outcome.exit_code != 0


@pytest.mark.asyncio
async def test_scheduler_close_cancels_and_awaits_owned_tasks() -> None:
    scheduler = AsyncioTaskScheduler(shutdown_timeout_seconds=1)
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def worker() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    await scheduler.start()
    scheduler.schedule(worker(), "owned-worker")
    await asyncio.wait_for(started.wait(), timeout=1)

    await scheduler.close()
    await scheduler.close()

    assert cleaned.is_set()
    assert scheduler.active_task_count == 0


@pytest.mark.asyncio
async def test_scheduler_starts_no_work_before_explicit_start() -> None:
    scheduler = AsyncioTaskScheduler(shutdown_timeout_seconds=1)

    async def worker() -> None:
        raise AssertionError("work must not start")

    with pytest.raises(RuntimeError, match="must be started"):
        scheduler.schedule(worker(), "too-early")

    assert scheduler.active_task_count == 0
    await scheduler.start()
    await scheduler.close()


@pytest.mark.asyncio
async def test_process_executor_close_stops_children_and_is_idempotent(tmp_path: Path) -> None:
    settings = EmrSettings.from_configuration(load_configuration("config/mystack.yaml"))
    executor = LocalProcessExecutor(settings)
    execution = asyncio.create_task(
        executor.execute(
            cluster_id="j-close",
            operation_id="s-close",
            command=[sys.executable, "-c", "import time; time.sleep(30)"],
            work_dir=tmp_path,
            timeout_seconds=30,
            environment={},
        )
    )
    await _wait_for_process(executor)

    await executor.close()
    await executor.close()
    outcome = await asyncio.wait_for(execution, timeout=1)

    assert outcome.exit_code != 0
    assert executor.active_process_count == 0


async def _wait_for_process(executor: LocalProcessExecutor) -> None:
    for _ in range(100):
        if executor.active_process_count:
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("child process was not registered")
