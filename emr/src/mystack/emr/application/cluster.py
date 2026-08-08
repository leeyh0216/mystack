"""EMR cluster command handler, separate from asynchronous execution.

Official command semantics:
https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_TerminateJobFlows.html
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from mystack.aws_protocol.observability import log_event
from mystack.emr.domain import Cluster, ClusterState, StateReason, StepState
from mystack.emr.domain.errors import (
    ActiveStepLimitExceededError,
    UnsupportedReleaseLabelError,
)
from mystack.emr.domain.model import ClusterTimeline
from mystack.emr.domain.repositories import ClusterRepository

from .commands import CreateCluster
from .policy import EmrPolicy
from .ports import Clock, IdGenerator, QueueDriver, StepRunner
from .step_factory import StepFactory
from .transitions import LifecycleTransitions

_LOGGER = logging.getLogger(__name__)


class ClusterCommandHandler:
    def __init__(
        self,
        repository: ClusterRepository,
        clock: Clock,
        ids: IdGenerator,
        step_runner: StepRunner,
        driver: QueueDriver,
        policy: EmrPolicy,
        transitions: LifecycleTransitions,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._step_runner = step_runner
        self._driver = driver
        self._policy = policy
        self._transitions = transitions
        self._steps = StepFactory(ids)
        self._ids = ids

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
        cluster.steps.extend(self._steps.create(command.steps, now))
        await self._repository.add(cluster)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.cluster.created",
            cluster_id=cluster.id,
            cluster_state=cluster.state,
            release_label=cluster.release_label,
            step_count=len(cluster.steps),
            side_effect=True,
        )
        self._driver.schedule(cluster.id)
        return cluster

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
            self._transitions.cluster(
                cluster,
                ClusterState.TERMINATING,
                StateReason("USER_REQUEST", "Terminated by user request"),
            )
            for step in cluster.steps:
                if step.state is StepState.PENDING:
                    self._transitions.step(
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
                    self._transitions.step(step, target, StateReason("USER_REQUEST", ""))
            await self._repository.save(cluster)
            await self._step_runner.cleanup(cluster.id)
            cluster = await self._repository.get(cluster.id)
            if cluster.state is ClusterState.TERMINATING:
                self._transitions.cluster(
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
