"""Minimal application-owned contracts consumed by EMR inbound adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from mystack.emr.application.commands import AddSteps, CreateCluster
from mystack.emr.domain import BootstrapAction, Cluster, ClusterState, Step, StepState


class EmrClusterCommands(Protocol):
    async def create_cluster(
        self,
        command: CreateCluster,
        *,
        region: str,
        account_id: str,
    ) -> Cluster: ...

    async def terminate_clusters(self, cluster_ids: Iterable[str]) -> None: ...

    async def set_termination_protection(
        self,
        cluster_ids: Iterable[str],
        enabled: bool,
    ) -> None: ...

    async def set_visible_to_all_users(
        self,
        cluster_ids: Iterable[str],
        visible: bool,
    ) -> None: ...

    async def add_tags(self, cluster_id: str, tags: dict[str, str]) -> None: ...

    async def remove_tags(self, cluster_id: str, keys: Iterable[str]) -> None: ...


class EmrStepCommands(Protocol):
    async def add_steps(self, command: AddSteps) -> list[Step]: ...

    async def cancel_steps(
        self,
        cluster_id: str,
        step_ids: Iterable[str],
    ) -> dict[str, str]: ...


class EmrQueries(Protocol):
    async def describe_cluster(self, cluster_id: str) -> Cluster: ...

    async def describe_step(self, cluster_id: str, step_id: str) -> Step: ...

    async def list_clusters(
        self,
        *,
        states: set[ClusterState] | None = None,
        created_after: float | None = None,
        created_before: float | None = None,
        marker: str | None = None,
    ) -> tuple[list[Cluster], str | None]: ...

    async def list_steps(
        self,
        cluster_id: str,
        *,
        states: set[StepState] | None = None,
        step_ids: set[str] | None = None,
        marker: str | None = None,
    ) -> tuple[list[Step], str | None]: ...

    async def list_bootstrap_actions(
        self,
        cluster_id: str,
        *,
        marker: str | None = None,
    ) -> tuple[list[BootstrapAction], str | None]: ...


class EmrManagementQueries(Protocol):
    async def list_clusters(
        self,
        *,
        states: set[ClusterState] | None = None,
        created_after: float | None = None,
        created_before: float | None = None,
        marker: str | None = None,
    ) -> tuple[list[Cluster], str | None]: ...

    async def describe_cluster(self, cluster_id: str) -> Cluster: ...
