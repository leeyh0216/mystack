"""EMR Step command handler, separate from queue execution.

Official command semantics:
https://docs.aws.amazon.com/emr/latest/APIReference/API_AddJobFlowSteps.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_CancelSteps.html
"""

from __future__ import annotations

from collections.abc import Iterable

from mystack.emr.application.commands import AddSteps
from mystack.emr.application.policy import EmrPolicy
from mystack.emr.application.ports import Clock, IdGenerator, QueueDriver, StepRunner
from mystack.emr.application.step_factory import StepFactory
from mystack.emr.application.transitions import LifecycleTransitions
from mystack.emr.domain import ClusterState, StateReason, Step, StepState
from mystack.emr.domain.errors import ActiveStepLimitExceededError, InvalidClusterStateError
from mystack.emr.domain.repositories import ClusterRepository


class StepCommandHandler:
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
        steps = self._steps.create(command.steps, self._clock.now())
        cluster.steps.extend(steps)
        if cluster.state is ClusterState.WAITING:
            self._transitions.cluster(cluster, ClusterState.RUNNING, StateReason("", ""))
        await self._repository.save(cluster)
        self._driver.schedule(cluster.id)
        return steps

    async def cancel_steps(self, cluster_id: str, step_ids: Iterable[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        for step_id in step_ids:
            cluster = await self._repository.get(cluster_id)
            step = cluster.step(step_id)
            if step.state is StepState.PENDING:
                self._transitions.step(
                    step,
                    StepState.CANCELLED,
                    StateReason("USER_REQUEST", ""),
                )
                await self._repository.save(cluster)
                results[step_id] = "SUBMITTED"
            elif step.state is StepState.RUNNING:
                self._transitions.step(
                    step,
                    StepState.CANCEL_PENDING,
                    StateReason("USER_REQUEST", "Cancellation requested"),
                )
                await self._repository.save(cluster)
                await self._step_runner.cancel(cluster_id, step_id)
                results[step_id] = "SUBMITTED"
            else:
                results[step_id] = "FAILED"
        return results
