"""EMR Step failure and empty-queue policy.

Official ActionOnFailure behavior:
https://docs.aws.amazon.com/emr/latest/APIReference/API_StepConfig.html
"""

from __future__ import annotations

from mystack.emr.domain import ActionOnFailure, Cluster, ClusterState, StateReason, Step, StepState
from mystack.emr.domain.repositories import ClusterRepository

from .ports import StepRunner
from .transitions import LifecycleTransitions


class QueueCompletionPolicy:
    def __init__(
        self,
        repository: ClusterRepository,
        step_runner: StepRunner,
        transitions: LifecycleTransitions,
    ) -> None:
        self._repository = repository
        self._step_runner = step_runner
        self._transitions = transitions

    async def apply_failure(self, cluster: Cluster, failed_step: Step) -> None:
        action = failed_step.action_on_failure
        if action is ActionOnFailure.CONTINUE:
            await self._repository.save(cluster)
            return
        for step in cluster.steps:
            if step.state is StepState.PENDING:
                self._transitions.step(
                    step,
                    StepState.CANCELLED,
                    StateReason("", f"Cancelled after failure of {failed_step.id}"),
                )
        if action is ActionOnFailure.CANCEL_AND_WAIT:
            self._transitions.cluster(
                cluster,
                ClusterState.WAITING,
                StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
            )
            await self._repository.save(cluster)
            return
        self._transitions.cluster(
            cluster,
            ClusterState.TERMINATING,
            StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
        )
        await self._repository.save(cluster)
        await self._step_runner.cleanup(cluster.id)
        cluster = await self._repository.get(cluster.id)
        self._transitions.cluster(
            cluster,
            ClusterState.TERMINATED_WITH_ERRORS,
            StateReason("STEP_FAILURE", f"Step {failed_step.id} failed"),
        )
        await self._repository.save(cluster)

    async def complete_empty_queue(self, cluster: Cluster) -> None:
        if cluster.state is ClusterState.WAITING:
            return
        if cluster.keep_alive:
            self._transitions.cluster(
                cluster,
                ClusterState.WAITING,
                StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
            )
            await self._repository.save(cluster)
            return
        self._transitions.cluster(
            cluster,
            ClusterState.TERMINATING,
            StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
        )
        await self._repository.save(cluster)
        await self._step_runner.cleanup(cluster.id)
        cluster = await self._repository.get(cluster.id)
        self._transitions.cluster(
            cluster,
            ClusterState.TERMINATED,
            StateReason("ALL_STEPS_COMPLETED", "All steps completed"),
        )
        await self._repository.save(cluster)
