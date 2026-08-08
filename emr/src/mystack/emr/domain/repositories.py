"""Repository port owned by the EMR domain.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/faq.html
"""

from __future__ import annotations

from typing import Protocol

from .model import Cluster


class ClusterRepository(Protocol):
    async def add(self, cluster: Cluster) -> None: ...

    async def get(self, cluster_id: str) -> Cluster: ...

    async def save(self, cluster: Cluster) -> None: ...

    async def list(self) -> list[Cluster]: ...
