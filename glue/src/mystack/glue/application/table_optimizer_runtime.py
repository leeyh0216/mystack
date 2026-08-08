"""Bounded scheduler for managed Glue Iceberg table optimizers.

Official behavior reference: https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.ports import TableOptimizerExecutor
from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork

_LOGGER = logging.getLogger(__name__)


class TableOptimizerRuntimeUseCases(Protocol):
    async def recover_interrupted_table_optimizer_runs(self, reason: str) -> int: ...

    async def claim_due_table_optimizer_work(self, maximum: int) -> list[TableOptimizerWork]: ...

    async def mark_table_optimizer_in_progress(self, work: TableOptimizerWork) -> bool: ...

    async def complete_table_optimizer(self, work: TableOptimizerWork, metrics: dict) -> bool: ...

    async def fail_table_optimizer(self, work: TableOptimizerWork, error: str) -> bool: ...

    async def is_table_optimizer_work_current(self, work: TableOptimizerWork) -> bool: ...


class TableOptimizerRuntime:
    """Own scheduler/task lifetime; application handlers own every durable transition."""

    def __init__(
        self,
        application: TableOptimizerRuntimeUseCases,
        executor: TableOptimizerExecutor,
        *,
        poll_interval_seconds: float,
        max_concurrent_runs: int,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("Optimizer runtime poll interval must be positive")
        if max_concurrent_runs <= 0:
            raise ValueError("Optimizer runtime concurrency must be positive")
        self._application = application
        self._executor = executor
        self._poll_interval_seconds = poll_interval_seconds
        self._max_concurrent_runs = max_concurrent_runs
        self._stop = asyncio.Event()
        self._scheduler: asyncio.Task[None] | None = None
        self._workers: dict[str, tuple[TableOptimizerWork, asyncio.Task[None]]] = {}

    async def start(self) -> None:
        if self._scheduler is not None:
            return
        recovered = await self._application.recover_interrupted_table_optimizer_runs(
            "Mystack Glue restarted while the optimizer run was active"
        )
        self._stop.clear()
        self._scheduler = asyncio.create_task(
            self._run(),
            name="glue-table-optimizer-scheduler",
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.table_optimizer.runtime.started",
            recovered_run_count=recovered,
            poll_interval_seconds=self._poll_interval_seconds,
            max_concurrent_runs=self._max_concurrent_runs,
            side_effect=True,
        )

    async def close(self) -> None:
        scheduler = self._scheduler
        if scheduler is None:
            return
        self._stop.set()
        scheduler.cancel()
        await asyncio.gather(scheduler, return_exceptions=True)
        workers = [task for _, task in self._workers.values()]
        for task in workers:
            task.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        self._scheduler = None
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.table_optimizer.runtime.stopped",
            interrupted_worker_count=len(workers),
            side_effect=True,
        )

    async def tick(self) -> None:
        await self._reap_and_cancel_stale()
        capacity = self._max_concurrent_runs - len(self._workers)
        if capacity <= 0:
            return
        for work in await self._application.claim_due_table_optimizer_work(capacity):
            task = asyncio.create_task(
                self._execute(work),
                name=f"glue-table-optimizer-{work.run_id}",
            )
            self._workers[work.run_id] = (work, task)
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.table_optimizer.worker.scheduled",
                run_id=work.run_id,
                optimizer_type=work.optimizer_type.value,
                active_worker_count=len(self._workers),
                side_effect=True,
            )

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log_event(
                    _LOGGER,
                    logging.ERROR,
                    "glue.table_optimizer.scheduler.failed",
                    exc_info=True,
                    side_effect=False,
                    fix_hint=(
                        "Inspect scheduler boundary logs and durable optimizer state; a newer "
                        "client protocol should not require changes in the runtime loop."
                    ),
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_seconds)
            except TimeoutError:
                pass

    async def _reap_and_cancel_stale(self) -> None:
        for run_id, (work, task) in list(self._workers.items()):
            if task.done():
                await asyncio.gather(task, return_exceptions=True)
                self._workers.pop(run_id, None)
                continue
            if not await self._application.is_table_optimizer_work_current(work):
                task.cancel()
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "glue.table_optimizer.worker.cancel.requested",
                    run_id=work.run_id,
                    reason="optimizer_deleted_or_reconfigured",
                    side_effect=True,
                )

    async def _execute(self, work: TableOptimizerWork) -> None:
        try:
            if not await self._application.mark_table_optimizer_in_progress(work):
                return
            result = await self._executor.execute(work)
            await self._application.complete_table_optimizer(work, result.metrics)
        except asyncio.CancelledError:
            await asyncio.shield(
                self._application.fail_table_optimizer(
                    work,
                    "Mystack interrupted the Spark optimizer process",
                )
            )
            raise
        except Exception as error:
            message = f"{type(error).__name__}: {error}"[:2048]
            await self._application.fail_table_optimizer(work, message)
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.table_optimizer.worker.failed",
                run_id=work.run_id,
                optimizer_type=work.optimizer_type.value,
                failure_type=type(error).__name__,
                side_effect=True,
                exc_info=True,
                fix_hint=(
                    "Inspect the per-run Spark stdout/stderr and executor command metadata. "
                    "If Glue 5 or Iceberg changed, update the Spark optimizer adapter only."
                ),
            )
