"""Asynchronous EMR bootstrap and Step queue driver.

The driver is the only application component that knows background scheduling and runners.
Official lifecycle references:
https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-work-with-steps.html
"""

from __future__ import annotations

import asyncio
import logging

from mystack.aws_protocol.observability import log_event
from mystack.emr.domain import ClusterState, StateReason, StepState
from mystack.emr.domain.repositories import ClusterRepository

from .failure import QueueCompletionPolicy
from .ports import BootstrapRunner, StepRunner, TaskScheduler
from .transitions import LifecycleTransitions

_LOGGER = logging.getLogger(__name__)


class ClusterQueueDriver:
    def __init__(
        self,
        repository: ClusterRepository,
        bootstrap_runner: BootstrapRunner,
        step_runner: StepRunner,
        scheduler: TaskScheduler,
        transitions: LifecycleTransitions,
        completion: QueueCompletionPolicy,
    ) -> None:
        self._repository = repository
        self._bootstrap_runner = bootstrap_runner
        self._step_runner = step_runner
        self._scheduler = scheduler
        self._transitions = transitions
        self._completion = completion
        self._worker_locks: dict[str, asyncio.Lock] = {}

    @property
    def active_lock_count(self) -> int:
        return len(self._worker_locks)

    async def start(self) -> None:
        await self._scheduler.start()

    def schedule(self, cluster_id: str) -> None:
        self._scheduler.schedule(self._drive(cluster_id), f"emr-cluster-{cluster_id}")

    async def close(self) -> None:
        await self._scheduler.close()
        self._worker_locks.clear()

    async def _drive(self, cluster_id: str) -> None:
        lock = self._worker_locks.setdefault(cluster_id, asyncio.Lock())
        if lock.locked():
            log_event(
                _LOGGER,
                logging.DEBUG,
                "emr.driver.duplicate.skipped",
                cluster_id=cluster_id,
                active_lock_count=len(self._worker_locks),
            )
            return
        try:
            async with lock:
                await self._drive_exclusively(cluster_id)
        except asyncio.CancelledError:
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.driver.cancelled",
                cluster_id=cluster_id,
                side_effect=True,
            )
            raise
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.driver.failed",
                cluster_id=cluster_id,
                fix_hint=(
                    "Inspect the cluster transition, runner, and scheduler events for this cluster."
                ),
                exc_info=True,
            )
            raise
        finally:
            if self._worker_locks.get(cluster_id) is lock and not lock.locked():
                self._worker_locks.pop(cluster_id, None)
                log_event(
                    _LOGGER,
                    logging.DEBUG,
                    "emr.driver.lock.released",
                    cluster_id=cluster_id,
                    active_lock_count=len(self._worker_locks),
                    side_effect=True,
                )

    async def _drive_exclusively(self, cluster_id: str) -> None:
        cluster = await self._repository.get(cluster_id)
        if cluster.state is ClusterState.STARTING:
            self._transitions.cluster(
                cluster,
                ClusterState.BOOTSTRAPPING,
                StateReason("", "Running bootstrap actions"),
            )
            await self._repository.save(cluster)
            result = await self._bootstrap_runner.run(cluster, cluster.bootstrap_actions)
            cluster = await self._repository.get(cluster_id)
            if cluster.state is not ClusterState.BOOTSTRAPPING:
                return
            if not result.succeeded:
                self._transitions.cluster(
                    cluster,
                    ClusterState.TERMINATED_WITH_ERRORS,
                    StateReason("BOOTSTRAP_FAILURE", result.reason),
                )
                await self._repository.save(cluster)
                return
            self._transitions.cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
            await self._repository.save(cluster)

        while True:
            cluster = await self._repository.get(cluster_id)
            if cluster.state not in {ClusterState.RUNNING, ClusterState.WAITING}:
                return
            pending = next(
                (step for step in cluster.steps if step.state is StepState.PENDING),
                None,
            )
            if pending is None:
                await self._completion.complete_empty_queue(cluster)
                return
            if cluster.state is ClusterState.WAITING:
                self._transitions.cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
            self._transitions.step(pending, StepState.RUNNING, StateReason("", ""))
            await self._repository.save(cluster)
            result = await self._step_runner.run(cluster, pending)
            cluster = await self._repository.get(cluster_id)
            step = cluster.step(pending.id)
            if step.state is StepState.CANCEL_PENDING:
                self._transitions.step(
                    step,
                    StepState.CANCELLED,
                    StateReason("USER_REQUEST", ""),
                )
                await self._repository.save(cluster)
                continue
            if step.state is not StepState.RUNNING:
                continue
            if result.succeeded:
                self._transitions.step(step, StepState.COMPLETED, StateReason("", ""))
                await self._repository.save(cluster)
                continue
            step.failure_details = {
                "Reason": result.reason,
                "Message": result.reason,
                "LogFile": result.log_file or "",
            }
            self._transitions.step(step, StepState.FAILED, StateReason("", result.reason))
            await self._completion.apply_failure(cluster, step)
