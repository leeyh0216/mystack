"""Glue application outbound ports.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class IdentifierGenerator(Protocol):
    """Generate an opaque identifier without coupling application code to UUID infrastructure."""

    def new(self) -> str: ...


class IcebergMetadataStore(Protocol):
    """Persist Iceberg metadata documents behind a storage-neutral application port."""

    async def read(self, location: str) -> dict[str, Any]: ...

    async def write(self, location: str, document: dict[str, Any]) -> None: ...

    async def delete(self, location: str) -> None: ...
