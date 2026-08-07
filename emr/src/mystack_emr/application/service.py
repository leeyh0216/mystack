"""EMR use cases and asynchronous cluster/Step orchestration.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-work-with-steps.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
from collections.abc import Iterable
from typing import TypeVar

from mystack_aws_protocol.observability import log_event

from mystack_emr.domain import (
    ActionOnFailure,
    BootstrapAction,
    Cluster,
    ClusterState,
    StateReason,
    Step,
    StepState,
)
from mystack_emr.domain.errors import (
    ActiveStepLimitExceededError,
    InvalidClusterStateError,
    UnsupportedReleaseLabelError,
)
from mystack_emr.domain.model import ClusterTimeline, StepSpec, StepTimeline
from mystack_emr.domain.repositories import ClusterRepository

from .commands import AddSteps, CreateCluster
from .policy import EmrPolicy
from .ports import BootstrapRunner, Clock, IdGenerator, StepRunner, TaskScheduler

_LOGGER = logging.getLogger(__name__)
_PageItem = TypeVar("_PageItem")


class EmrApplication:
    def __init__(
        self,
        repository: ClusterRepository,
        clock: Clock,
        ids: IdGenerator,
        bootstrap_runner: BootstrapRunner,
        step_runner: StepRunner,
        scheduler: TaskScheduler,
        policy: EmrPolicy,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._ids = ids
        self._bootstrap_runner = bootstrap_runner
        self._step_runner = step_runner
        self._scheduler = scheduler
        self._policy = policy
        self._worker_locks: dict[str, asyncio.Lock] = {}

    async def create_cluster(
        self,
        command: CreateCluster,
        *,
        region: str,
        account_id: str,
    ) -> Cluster:
        release_label = command.release_label or self._policy.default_release_label
        if release_label not in self._policy.release_profiles:
            raise UnsupportedReleaseLabelError(
                f"Release label {release_label!r} is not configured. "
                f"Configured labels: {sorted(self._policy.release_profiles)}"
            )
        if len(command.steps) > self._policy.max_active_steps:
            raise ActiveStepLimitExceededError(
                f"A cluster cannot have more than {self._policy.max_active_steps} active steps"
            )
        now = self._clock.now()
        cluster_id = self._ids.cluster_id()
        cluster = Cluster(
            id=cluster_id,
            arn=f"arn:aws:elasticmapreduce:{region}:{account_id}:cluster/{cluster_id}",
            name=command.name,
            release_label=release_label,
            state=ClusterState.STARTING,
            reason=StateReason("", ""),
            timeline=ClusterTimeline(creation=now),
            keep_alive=command.keep_alive,
            termination_protected=command.termination_protected,
            visible_to_all_users=command.visible_to_all_users,
            step_concurrency_level=command.step_concurrency_level,
            instance_config=command.instance_config,
            applications=command.applications,
            bootstrap_actions=command.bootstrap_actions,
            tags=dict(command.tags),
            log_uri=command.log_uri,
            service_role=command.service_role,
        )
        cluster.steps.extend(self._new_steps(command.steps, now))
        await self._repository.add(cluster)
        self._log_transition(cluster, None, ClusterState.STARTING, "cluster created")
        self._schedule(cluster.id)
        return cluster

    async def describe_cluster(self, cluster_id: str) -> Cluster:
        return await self._repository.get(cluster_id)

    async def describe_step(self, cluster_id: str, step_id: str) -> Step:
        return (await self._repository.get(cluster_id)).step(step_id)

    async def add_steps(self, command: AddSteps) -> list[Step]:
        cluster = await self._repository.get(command.cluster_id)
        if cluster.state not in {ClusterState.RUNNING, ClusterState.WAITING}:
            raise InvalidClusterStateError(
                f"Cannot add steps to cluster {cluster.id} in state {cluster.state}"
            )
        if cluster.active_step_count() + len(command.steps) > self._policy.max_active_steps:
            raise ActiveStepLimitExceededError(
                f"A cluster cannot have more than {self._policy.max_active_steps} active steps"
            )
        steps = self._new_steps(command.steps, self._clock.now())
        cluster.steps.extend(steps)
        if cluster.state is ClusterState.WAITING:
            self._transition_cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
        await self._repository.save(cluster)
        self._schedule(cluster.id)
        return steps

    async def list_clusters(
        self,
        *,
        states: set[ClusterState] | None = None,
        created_after: float | None = None,
        created_before: float | None = None,
        marker: str | None = None,
    ) -> tuple[list[Cluster], str | None]:
        clusters = sorted(
            await self._repository.list(),
            key=lambda cluster: cluster.timeline.creation,
            reverse=True,
        )
        filtered = [
            cluster
            for cluster in clusters
            if (not states or cluster.state in states)
            and (created_after is None or cluster.timeline.creation >= created_after)
            and (created_before is None or cluster.timeline.creation <= created_before)
        ]
        return self._page(filtered, marker)

    async def list_steps(
        self,
        cluster_id: str,
        *,
        states: set[StepState] | None = None,
        step_ids: set[str] | None = None,
        marker: str | None = None,
    ) -> tuple[list[Step], str | None]:
        cluster = await self._repository.get(cluster_id)
        filtered = [
            step
            for step in reversed(cluster.steps)
            if (not states or step.state in states) and (not step_ids or step.id in step_ids)
        ]
        return self._page(filtered, marker)

    async def list_bootstrap_actions(
        self,
        cluster_id: str,
        *,
        marker: str | None = None,
    ) -> tuple[list[BootstrapAction], str | None]:
        cluster = await self._repository.get(cluster_id)
        return self._page(list(cluster.bootstrap_actions), marker)

    async def cancel_steps(self, cluster_id: str, step_ids: Iterable[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        for step_id in step_ids:
            cluster = await self._repository.get(cluster_id)
            step = cluster.step(step_id)
            if step.state is StepState.PENDING:
                self._transition_step(step, StepState.CANCELLED, StateReason("USER_REQUEST", ""))
                await self._repository.save(cluster)
                results[step_id] = "SUBMITTED"
            elif step.state is StepState.RUNNING:
                self._transition_step(
                    step,
                    StepState.CANCEL_PENDING,
                    StateReason("USER_REQUEST", "Cancellation requested"),
                )
                await self._repository.save(cluster)
                await self._step_runner.cancel(cluster_id, step_id)
                cluster = await self._repository.get(cluster_id)
                step = cluster.step(step_id)
                if step.state is StepState.CANCEL_PENDING:
                    self._transition_step(
                        step,
                        StepState.CANCELLED,
                        StateReason("USER_REQUEST", ""),
                    )
                    await self._repository.save(cluster)
                results[step_id] = "SUBMITTED"
            else:
                results[step_id] = "FAILED"
        return results

    async def terminate_clusters(self, cluster_ids: Iterable[str]) -> None:
        for cluster_id in cluster_ids:
            cluster = await self._repository.get(cluster_id)
            if cluster.termination_protected or cluster.terminal:
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.cluster.termination.skipped",
                    cluster_id=cluster.id,
                    state=cluster.state,
                    termination_protected=cluster.termination_protected,
                )
                continue
            self._transition_cluster(
                cluster,
                ClusterState.TERMINATING,
                StateReason("USER_REQUEST", "Terminated by user request"),
            )
            for step in cluster.steps:
                if step.state is StepState.PENDING:
                    self._transition_step(
                        step,
                        StepState.CANCELLED,
                        StateReason("USER_REQUEST", ""),
                    )
                elif step.state in {StepState.RUNNING, StepState.CANCEL_PENDING}:
                    await self._step_runner.cancel(cluster.id, step.id)
                    target = (
                        StepState.INTERRUPTED
                        if step.state is StepState.RUNNING
                        else StepState.CANCELLED
                    )
                    self._transition_step(step, target, StateReason("USER_REQUEST", ""))
            await self._repository.save(cluster)
            await self._step_runner.cleanup(cluster.id)
            cluster = await self._repository.get(cluster.id)
            if cluster.state is ClusterState.TERMINATING:
                self._transition_cluster(
                    cluster,
                    ClusterState.TERMINATED,
                    StateReason("USER_REQUEST", "Terminated by user request"),
                )
                await self._repository.save(cluster)

    async def set_termination_protection(
        self,
        cluster_ids: Iterable[str],
        enabled: bool,
    ) -> None:
        for cluster_id in cluster_ids:
            cluster = await self._repository.get(cluster_id)
            cluster.termination_protected = enabled
            await self._repository.save(cluster)

    async def set_visible_to_all_users(
        self,
        cluster_ids: Iterable[str],
        visible: bool,
    ) -> None:
        for cluster_id in cluster_ids:
            cluster = await self._repository.get(cluster_id)
            cluster.visible_to_all_users = visible
            await self._repository.save(cluster)

    async def add_tags(self, cluster_id: str, tags: dict[str, str]) -> None:
        cluster = await self._repository.get(cluster_id)
        cluster.tags.update(tags)
        await self._repository.save(cluster)

    async def remove_tags(self, cluster_id: str, keys: Iterable[str]) -> None:
        cluster = await self._repository.get(cluster_id)
        for key in keys:
            cluster.tags.pop(key, None)
        await self._repository.save(cluster)

    def _schedule(self, cluster_id: str) -> None:
        self._scheduler.start(self._drive(cluster_id), f"emr-cluster-{cluster_id}")

    async def _drive(self, cluster_id: str) -> None:
        lock = self._worker_locks.setdefault(cluster_id, asyncio.Lock())
        if lock.locked():
            return
        async with lock:
            cluster = await self._repository.get(cluster_id)
            if cluster.state is ClusterState.STARTING:
                self._transition_cluster(
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
                    self._transition_cluster(
                        cluster,
                        ClusterState.TERMINATED_WITH_ERRORS,
                        StateReason("BOOTSTRAP_FAILURE", result.reason),
                    )
                    await self._repository.save(cluster)
                    return
                self._transition_cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
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
                    await self._complete_queue(cluster)
                    return
                if cluster.state is ClusterState.WAITING:
                    self._transition_cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
                self._transition_step(pending, StepState.RUNNING, StateReason("", ""))
                await self._repository.save(cluster)
                result = await self._step_runner.run(cluster, pending)
                cluster = await self._repository.get(cluster_id)
                step = cluster.step(pending.id)
                if step.state is not StepState.RUNNING:
                    continue
                if result.succeeded:
                    self._transition_step(step, StepState.COMPLETED, StateReason("", ""))
                    await self._repository.save(cluster)
                    continue
                step.failure_details = {
                    "Reason": result.reason,
                    "Message": result.reason,
                    "LogFile": result.log_file or "",
                }
                self._transition_step(
                    step,
                    StepState.FAILED,
                    StateReason("", result.reason),
                )
                await self._apply_step_failure(cluster, step)

    async def _apply_step_failure(self, cluster: Cluster, failed_step: Step) -> None:
        action = failed_step.action_on_failure
        if action is ActionOnFailure.CONTINUE:
            await self._repository.save(cluster)
            return
        for step in cluster.steps:
            if step.state is StepState.PENDING:
                self._transition_step(
                    step,
                    StepState.CANCELLED,
                    StateReason("", f"Cancelled after failure of {failed_step.id}"),
                )
        if action is ActionOnFailure.CANCEL_AND_WAIT:
            self._transition_cluster(
                cluster,
                ClusterState.WAITING,
                StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
            )
            await self._repository.save(cluster)
            return
        self._transition_cluster(
            cluster,
            ClusterState.TERMINATING,
            StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
        )
        await self._repository.save(cluster)
        await self._step_runner.cleanup(cluster.id)
        cluster = await self._repository.get(cluster.id)
        self._transition_cluster(
            cluster,
            ClusterState.TERMINATED_WITH_ERRORS,
            StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
        )
        await self._repository.save(cluster)

    async def _complete_queue(self, cluster: Cluster) -> None:
        if cluster.state is ClusterState.WAITING:
            return
        if cluster.keep_alive:
            self._transition_cluster(
                cluster,
                ClusterState.WAITING,
                StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
            )
            await self._repository.save(cluster)
            return
        self._transition_cluster(
            cluster,
            ClusterState.TERMINATING,
            StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
        )
        await self._repository.save(cluster)
        await self._step_runner.cleanup(cluster.id)
        cluster = await self._repository.get(cluster.id)
        self._transition_cluster(
            cluster,
            ClusterState.TERMINATED,
            StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
        )
        await self._repository.save(cluster)

    def _new_steps(self, specs: Iterable[StepSpec], now: float) -> list[Step]:
        return [
            Step(
                id=self._ids.step_id(),
                name=spec.name,
                config=spec.config,
                action_on_failure=spec.action_on_failure,
                state=StepState.PENDING,
                reason=StateReason("", ""),
                timeline=StepTimeline(creation=now),
            )
            for spec in specs
        ]

    def _transition_cluster(
        self,
        cluster: Cluster,
        state: ClusterState,
        reason: StateReason,
    ) -> None:
        before = cluster.state
        cluster.transition(state, self._clock.now(), reason)
        self._log_transition(cluster, before, state, reason.code or reason.message)

    def _transition_step(self, step: Step, state: StepState, reason: StateReason) -> None:
        before = step.state
        step.transition(state, self._clock.now(), reason)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step.state.transitioned",
            step_id=step.id,
            state_before=before,
            state_after=state,
            reason_code=reason.code,
            reason_message=reason.message,
        )

    @staticmethod
    def _log_transition(
        cluster: Cluster,
        before: ClusterState | None,
        after: ClusterState,
        reason: str,
    ) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.cluster.state.transitioned",
            cluster_id=cluster.id,
            state_before=before,
            state_after=after,
            reason=reason,
        )

    def _page(
        self,
        items: list[_PageItem],
        marker: str | None,
    ) -> tuple[list[_PageItem], str | None]:
        offset = _decode_marker(marker)
        page = items[offset : offset + self._policy.api_page_size]
        next_offset = offset + len(page)
        next_marker = _encode_marker(next_offset) if next_offset < len(items) else None
        return page, next_marker


def _encode_marker(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_marker(marker: str | None) -> int:
    if not marker:
        return 0
    try:
        return int(base64.urlsafe_b64decode(marker.encode()).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidClusterStateError("Invalid pagination marker") from error
