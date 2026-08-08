"""Repository port owned by the Glue domain.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from .model import CatalogState


class CatalogRepository(Protocol):
    async def snapshot(self) -> CatalogState: ...

    def transaction(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
    ) -> AbstractAsyncContextManager[CatalogState]: ...
