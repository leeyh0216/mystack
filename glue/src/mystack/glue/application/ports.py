"""Glue application outbound ports.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork


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


@dataclass(frozen=True, slots=True)
class TableOptimizerExecutionResult:
    metrics: dict[str, Any]


class TableOptimizerExecutor(Protocol):
    """Side-effect port for one bounded Spark optimizer invocation."""

    async def execute(self, work: TableOptimizerWork) -> TableOptimizerExecutionResult: ...
