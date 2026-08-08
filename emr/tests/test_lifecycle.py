"""EMR runtime partial-startup and driver-failure cleanup contracts.

Python cancellation reference:
https://docs.python.org/3/library/asyncio-task.html#task-cancellation
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from mystack.emr.adapters.outbound import AsyncioTaskScheduler, InMemoryClusterRepository
from mystack.emr.application.driver import ClusterQueueDriver
from mystack.emr.application.failure import QueueCompletionPolicy
from mystack.emr.application.ports import RuntimeResult
from mystack.emr.application.transitions import LifecycleTransitions
from mystack.emr.runtime import EmrRuntime, RuntimeState


class _Clock:
    def now(self) -> float:
        return 1.0


class _Runner:
    async def run(self, cluster, value) -> RuntimeResult:
        del cluster, value
        return RuntimeResult(True)

    async def cancel(self, cluster_id: str, step_id: str) -> None:
        del cluster_id, step_id

    async def cleanup(self, cluster_id: str) -> None:
        del cluster_id


class _CloseRecorder:
    active_process_count = 0

    def __init__(self, name: str, events: list[str], *, fail_start: bool = False) -> None:
        self._name = name
        self._events = events
        self._fail_start = fail_start

    async def start(self) -> None:
        self._events.append(f"start:{self._name}")
        if self._fail_start:
            raise RuntimeError("startup failed")

    async def close(self) -> None:
        self._events.append(f"close:{self._name}")


@pytest.mark.asyncio
async def test_partial_startup_closes_every_owned_resource_in_order(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = EmrRuntime(
        application=_CloseRecorder("application", events, fail_start=True),  # type: ignore[arg-type]
        _executor=_CloseRecorder("executor", events),  # type: ignore[arg-type]
        _artifacts=_CloseRecorder("artifacts", events),  # type: ignore[arg-type]
        _logs=_CloseRecorder("logs", events),  # type: ignore[arg-type]
        _settings=SimpleNamespace(work_root=tmp_path),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="startup failed"):
        await runtime.start()
    await runtime.close()

    assert events == [
        "start:application",
        "close:application",
        "close:executor",
        "close:logs",
        "close:artifacts",
    ]
    assert runtime.state is RuntimeState.CLOSED


@pytest.mark.asyncio
async def test_driver_runtime_failure_releases_task_and_cluster_lock() -> None:
    repository = InMemoryClusterRepository()
    scheduler = AsyncioTaskScheduler(shutdown_timeout_seconds=1)
    runner = _Runner()
    transitions = LifecycleTransitions(_Clock())
    completion = QueueCompletionPolicy(repository, runner, transitions)
    driver = ClusterQueueDriver(
        repository,
        runner,
        runner,
        scheduler,
        transitions,
        completion,
    )
    await driver.start()

    driver.schedule("j-missing")
    for _ in range(100):
        if scheduler.active_task_count == 0:
            break
        await asyncio.sleep(0.01)

    assert scheduler.active_task_count == 0
    assert driver.active_lock_count == 0
    await driver.close()
    await driver.close()
