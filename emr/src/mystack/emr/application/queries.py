"""Read-only EMR query handler.

Official APIs:
https://docs.aws.amazon.com/emr/latest/APIReference/API_DescribeCluster.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_ListSteps.html
"""

from __future__ import annotations

from mystack.emr.application.pagination import Paginator
from mystack.emr.domain import BootstrapAction, Cluster, ClusterState, Step, StepState
from mystack.emr.domain.repositories import ClusterRepository


class EmrQueryHandler:
    def __init__(self, repository: ClusterRepository, paginator: Paginator) -> None:
        self._repository = repository
        self._paginator = paginator

    async def describe_cluster(self, cluster_id: str) -> Cluster:
        return await self._repository.get(cluster_id)

    async def describe_step(self, cluster_id: str, step_id: str) -> Step:
        return (await self._repository.get(cluster_id)).step(step_id)

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
        return self._paginator.page(filtered, marker)

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
        return self._paginator.page(filtered, marker)

    async def list_bootstrap_actions(
        self,
        cluster_id: str,
        *,
        marker: str | None = None,
    ) -> tuple[list[BootstrapAction], str | None]:
        cluster = await self._repository.get(cluster_id)
        return self._paginator.page(list(cluster.bootstrap_actions), marker)
