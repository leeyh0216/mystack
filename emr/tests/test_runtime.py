"""Subprocess race regression tests.

References:
- https://docs.python.org/3/library/asyncio-subprocess.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_CancelSteps.html
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from mystack.aws_protocol import load_configuration
from mystack.emr.adapters.outbound import AsyncioTaskScheduler, LocalProcessExecutor
from mystack.emr.adapters.outbound.runtime import LocalSparkStepRunner
from mystack.emr.application.ports import RuntimeResult
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


@pytest.mark.asyncio
async def test_local_spark_runner_records_the_exact_resolved_argument_vector(
    tmp_path: Path,
) -> None:
    class Artifacts:
        async def materialize(self, uri: str, destination: Path) -> Path:
            return destination / Path(uri).name

    class Executor:
        def __init__(self) -> None:
            self.command: list[str] = []

        async def execute(self, **values):
            self.command = values["command"]
            return SimpleNamespace(
                exit_code=0,
                stdout_file=tmp_path / "stdout.log",
                stderr_file=tmp_path / "stderr.log",
            )

        async def cancel(self, cluster_id: str, step_id: str) -> None:
            del cluster_id, step_id

        async def cancel_cluster(self, cluster_id: str) -> None:
            del cluster_id

    class Journal:
        async def begin(self, cluster, step, work_dir: Path) -> None:
            del cluster, step
            work_dir.mkdir(parents=True)

        async def complete(self, cluster, step, work_dir, result, *, process_started) -> None:
            del cluster, step, work_dir, result, process_started

    executor = Executor()
    settings = SimpleNamespace(
        work_root=tmp_path,
        process_timeout_seconds=10,
        command_runner_jars=frozenset({"command-runner.jar"}),
        policy=SimpleNamespace(
            release_profiles={"emr-test": SimpleNamespace(runtime_profile="spark-test")}
        ),
        runtimes={
            "spark-test": SimpleNamespace(
                spark_submit="/opt/spark/bin/spark-submit",
                master="local[*]",
                packages=(),
                conf=(),
                submit_aliases=("spark-submit",),
                option_value_names=frozenset(),
            )
        },
        object_store=SimpleNamespace(
            endpoint_url="http://localstack:4566",
            region="us-east-1",
            access_key_id="test",
            secret_access_key="test",
            s3_path_style=True,
        ),
    )
    runner = LocalSparkStepRunner(
        settings,  # type: ignore[arg-type]
        Artifacts(),  # type: ignore[arg-type]
        executor,  # type: ignore[arg-type]
        Journal(),  # type: ignore[arg-type]
    )
    cluster = SimpleNamespace(id="j-1", release_label="emr-test")
    step = SimpleNamespace(
        id="s-1",
        config=SimpleNamespace(
            jar="command-runner.jar",
            args=("spark-submit", "s3://assets/job.py", "--mode", "verify"),
            properties=(),
            main_class=None,
        ),
    )

    result: RuntimeResult = await runner.run(cluster, step)  # type: ignore[arg-type]

    recorded = json.loads((tmp_path / "j-1" / "s-1" / "resolved-command.json").read_text())
    assert result.succeeded is True
    assert recorded["arguments"] == executor.command
    assert recorded["arguments"][0] == "/opt/spark/bin/spark-submit"
    assert recorded["arguments"][-2:] == ["--mode", "verify"]


async def _wait_for_process(executor: LocalProcessExecutor) -> None:
    for _ in range(100):
        if executor.active_process_count:
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("child process was not registered")
