"""Delegation-only EMR application facade and lifecycle owner.

The focused handlers implement the official EMR command/query semantics while this facade
preserves a compact composition API for the FastAPI root and tests.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from collections.abc import Iterable

from mystack.emr.domain import BootstrapAction, Cluster, ClusterState, Step, StepState
from mystack.emr.domain.repositories import ClusterRepository

from .cluster import ClusterCommandHandler
from .commands import AddSteps, CreateCluster
from .driver import ClusterQueueDriver
from .failure import QueueCompletionPolicy
from .pagination import Paginator
from .policy import EmrPolicy
from .ports import BootstrapRunner, Clock, IdGenerator, StepRunner, TaskScheduler
from .queries import EmrQueryHandler
from .step import StepCommandHandler
from .transitions import LifecycleTransitions


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
        transitions = LifecycleTransitions(clock)
        completion = QueueCompletionPolicy(repository, step_runner, transitions)
        self._driver = ClusterQueueDriver(
            repository,
            bootstrap_runner,
            step_runner,
            scheduler,
            transitions,
            completion,
        )
        self._cluster_commands = ClusterCommandHandler(
            repository,
            clock,
            ids,
            step_runner,
            self._driver,
            policy,
            transitions,
        )
        self._step_commands = StepCommandHandler(
            repository,
            clock,
            ids,
            step_runner,
            self._driver,
            policy,
            transitions,
        )
        self._queries = EmrQueryHandler(repository, Paginator(policy.api_page_size))

    @property
    def active_driver_lock_count(self) -> int:
        return self._driver.active_lock_count

    async def start(self) -> None:
        await self._driver.start()

    async def close(self) -> None:
        await self._driver.close()

    async def create_cluster(
        self,
        command: CreateCluster,
        *,
        region: str,
        account_id: str,
    ) -> Cluster:
        return await self._cluster_commands.create_cluster(
            command,
            region=region,
            account_id=account_id,
        )

    async def describe_cluster(self, cluster_id: str) -> Cluster:
        return await self._queries.describe_cluster(cluster_id)

    async def describe_step(self, cluster_id: str, step_id: str) -> Step:
        return await self._queries.describe_step(cluster_id, step_id)

    async def add_steps(self, command: AddSteps) -> list[Step]:
        return await self._step_commands.add_steps(command)

    async def list_clusters(
        self,
        *,
        states: set[ClusterState] | None = None,
        created_after: float | None = None,
        created_before: float | None = None,
        marker: str | None = None,
    ) -> tuple[list[Cluster], str | None]:
        return await self._queries.list_clusters(
            states=states,
            created_after=created_after,
            created_before=created_before,
            marker=marker,
        )

    async def list_steps(
        self,
        cluster_id: str,
        *,
        states: set[StepState] | None = None,
        step_ids: set[str] | None = None,
        marker: str | None = None,
    ) -> tuple[list[Step], str | None]:
        return await self._queries.list_steps(
            cluster_id,
            states=states,
            step_ids=step_ids,
            marker=marker,
        )

    async def list_bootstrap_actions(
        self,
        cluster_id: str,
        *,
        marker: str | None = None,
    ) -> tuple[list[BootstrapAction], str | None]:
        return await self._queries.list_bootstrap_actions(cluster_id, marker=marker)

    async def cancel_steps(self, cluster_id: str, step_ids: Iterable[str]) -> dict[str, str]:
        return await self._step_commands.cancel_steps(cluster_id, step_ids)

    async def terminate_clusters(self, cluster_ids: Iterable[str]) -> None:
        await self._cluster_commands.terminate_clusters(cluster_ids)

    async def set_termination_protection(
        self,
        cluster_ids: Iterable[str],
        enabled: bool,
    ) -> None:
        await self._cluster_commands.set_termination_protection(cluster_ids, enabled)

    async def set_visible_to_all_users(
        self,
        cluster_ids: Iterable[str],
        visible: bool,
    ) -> None:
        await self._cluster_commands.set_visible_to_all_users(cluster_ids, visible)

    async def add_tags(self, cluster_id: str, tags: dict[str, str]) -> None:
        await self._cluster_commands.add_tags(cluster_id, tags)

    async def remove_tags(self, cluster_id: str, keys: Iterable[str]) -> None:
        await self._cluster_commands.remove_tags(cluster_id, keys)
