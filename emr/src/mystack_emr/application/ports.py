"""Outbound ports consumed by EMR application orchestration.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

from mystack_emr.domain import BootstrapAction, Cluster, Step


class Clock(Protocol):
    def now(self) -> float: ...


class IdGenerator(Protocol):
    def cluster_id(self) -> str: ...

    def step_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    succeeded: bool
    exit_code: int | None = None
    reason: str = ""
    log_file: str | None = None


class BootstrapRunner(Protocol):
    async def run(
        self,
        cluster: Cluster,
        actions: tuple[BootstrapAction, ...],
    ) -> RuntimeResult: ...


class StepRunner(Protocol):
    async def run(self, cluster: Cluster, step: Step) -> RuntimeResult: ...

    async def cancel(self, cluster_id: str, step_id: str) -> None: ...

    async def cleanup(self, cluster_id: str) -> None: ...


class TaskScheduler(Protocol):
    def start(self, work: Coroutine[Any, Any, None], name: str) -> None: ...
