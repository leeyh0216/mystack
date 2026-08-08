"""Bounded managed optimizer scheduler and Spark process adapter contracts.

References:
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
- https://docs.python.org/3/library/asyncio-subprocess.html
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import mystack.glue.runtime.table_optimizer_job as optimizer_job
import pytest
from mystack.aws_protocol import load_configuration
from mystack.glue.adapters.outbound import (
    SparkTableOptimizerExecutor,
    SparkTableOptimizerExecutorSettings,
)
from mystack.glue.application.ports import TableOptimizerExecutionResult
from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork
from mystack.glue.application.table_optimizer_runtime import TableOptimizerRuntime
from mystack.glue.config import GlueSettings


def _work(run_id: str = "run-1") -> TableOptimizerWork:
    return TableOptimizerWork(
        key=("000000000000", "db", "table", "compaction"),
        run_id=run_id,
        configuration_revision=0,
        configuration={
            "enabled": True,
            "compactionConfiguration": {
                "icebergConfiguration": {
                    "strategy": "binpack",
                    "minInputFiles": 1,
                    "deleteFileThreshold": 1,
                }
            },
        },
        table_location="s3://warehouse/db/table",
        optimizer_create_time=1.0,
    )


def test_optimizer_runtime_settings_are_loaded_from_the_mounted_yaml() -> None:
    settings = GlueSettings.from_configuration(load_configuration("config/mystack.yaml"))

    assert settings.table_optimizers.enabled is True
    assert settings.table_optimizers.work_root == (settings.data_root / "table-optimizer-runs")
    assert settings.table_optimizers.worker.submit_args == ("--master", "local[*]")
    assert settings.table_optimizers.policy.compaction_failure_limit == 4


def test_zorder_uses_the_current_identity_sort_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        @staticmethod
        def collect() -> list:
            return [
                type(
                    "Row",
                    (),
                    {"asDict": lambda self, recursive: {"rewritten_data_files_count": 2}},
                )()
            ]

    class Spark:
        def __init__(self) -> None:
            self.statement = ""

        def sql(self, statement: str) -> Result:
            self.statement = statement
            return Result()

    work = {
        "database_name": "db",
        "table_name": "table",
        "configuration": {
            "compactionConfiguration": {
                "icebergConfiguration": {
                    "strategy": "z-order",
                    "minInputFiles": 2,
                    "deleteFileThreshold": 1,
                }
            }
        },
    }
    monkeypatch.setattr(
        optimizer_job,
        "_default_sort_columns",
        lambda *args: ("category", "quoted`column"),
    )
    spark = Spark()

    metrics = optimizer_job._compact(spark, work, "mystack")

    assert metrics["NumberOfFilesCompacted"] == 2
    assert "strategy => 'sort'" in spark.statement
    assert "sort_order => 'zorder(`category`,`quoted``column`)'" in spark.statement


class RecordingApplication:
    def __init__(self, work: TableOptimizerWork) -> None:
        self.work = work
        self.claimed = False
        self.current = True
        self.recovered = 0
        self.completed: list[dict] = []
        self.failures: list[str] = []
        self.terminal = asyncio.Event()

    async def recover_interrupted_table_optimizer_runs(self, reason: str) -> int:
        del reason
        self.recovered += 1
        return 0

    async def claim_due_table_optimizer_work(self, maximum: int) -> list[TableOptimizerWork]:
        if maximum > 0 and not self.claimed:
            self.claimed = True
            return [self.work]
        return []

    async def mark_table_optimizer_in_progress(self, work: TableOptimizerWork) -> bool:
        return self.current and work == self.work

    async def complete_table_optimizer(self, work: TableOptimizerWork, metrics: dict) -> bool:
        assert work == self.work
        self.completed.append(metrics)
        self.terminal.set()
        return True

    async def fail_table_optimizer(self, work: TableOptimizerWork, error: str) -> bool:
        assert work == self.work
        self.failures.append(error)
        self.terminal.set()
        return True

    async def is_table_optimizer_work_current(self, work: TableOptimizerWork) -> bool:
        return self.current and work == self.work


class CompletingExecutor:
    async def execute(self, work: TableOptimizerWork) -> TableOptimizerExecutionResult:
        assert work.optimizer_type.value == "compaction"
        return TableOptimizerExecutionResult({"NumberOfFilesCompacted": 2})


class BlockingExecutor:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def execute(self, work: TableOptimizerWork) -> TableOptimizerExecutionResult:
        del work
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


async def test_runtime_claims_executes_and_records_one_terminal_result() -> None:
    application = RecordingApplication(_work())
    runtime = TableOptimizerRuntime(
        application,
        CompletingExecutor(),
        poll_interval_seconds=1.0,
        max_concurrent_runs=1,
    )

    await runtime.tick()
    await asyncio.wait_for(application.terminal.wait(), timeout=1.0)
    await runtime.tick()

    assert application.completed == [{"NumberOfFilesCompacted": 2}]
    assert application.failures == []


async def test_runtime_shutdown_cancels_worker_and_records_failed_run() -> None:
    application = RecordingApplication(_work())
    executor = BlockingExecutor()
    runtime = TableOptimizerRuntime(
        application,
        executor,
        poll_interval_seconds=0.01,
        max_concurrent_runs=1,
    )
    await runtime.start()
    await asyncio.wait_for(executor.started.wait(), timeout=1.0)

    await asyncio.wait_for(runtime.close(), timeout=1.0)

    assert application.recovered == 1
    assert application.completed == []
    assert application.failures == ["Mystack interrupted the Spark optimizer process"]


async def test_spark_executor_decodes_marker_and_writes_per_run_logs(tmp_path: Path) -> None:
    executor = SparkTableOptimizerExecutor(
        _executor_settings(
            tmp_path,
            (
                "-c",
                "printf '%s\\n' 'MYSTACK_TABLE_OPTIMIZER_RESULT="
                '{"metrics":{"NumberOfFilesCompacted":3}}\'',
            ),
        )
    )

    result = await executor.execute(_work())

    assert result.metrics == {"NumberOfFilesCompacted": 3}
    assert (tmp_path / "run-1" / "work.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "run-1" / "stdout.log").is_file()
    assert (tmp_path / "run-1" / "stderr.log").is_file()


async def test_spark_executor_enforces_configured_process_timeout(tmp_path: Path) -> None:
    executor = SparkTableOptimizerExecutor(
        _executor_settings(tmp_path, ("-c", "sleep 60"), timeout_seconds=0.05)
    )

    with pytest.raises(TimeoutError, match="exceeded 0.05 seconds"):
        await executor.execute(_work("timeout-run"))


def _executor_settings(
    work_root: Path,
    submit_args: tuple[str, ...],
    *,
    timeout_seconds: float = 1.0,
) -> SparkTableOptimizerExecutorSettings:
    return SparkTableOptimizerExecutorSettings(
        spark_submit=Path("/bin/sh"),
        submit_args=submit_args,
        work_root=work_root,
        timeout_seconds=timeout_seconds,
        terminate_grace_seconds=0.05,
        catalog_endpoint_url="http://127.0.0.1:8080",
        object_store_endpoint_url="http://127.0.0.1:4566",
        region="us-east-1",
        access_key_id="test",
        secret_access_key="test",
        catalog_name="mystack",
    )
