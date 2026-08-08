"""Versioned operation-middleware contract shared by service composition roots.

Python protocol and plugin-discovery references:
- https://docs.python.org/3/library/typing.html#typing.Protocol
- https://docs.python.org/3/library/importlib.metadata.html#entry-points
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from .context import AwsRequestContext


@dataclass(frozen=True, slots=True)
class OperationCall:
    """One validated AWS operation call crossing an extension boundary."""

    operation: str
    payload: Mapping[str, Any]
    context: AwsRequestContext

    def with_payload(self, payload: Mapping[str, Any]) -> OperationCall:
        return replace(self, payload=payload)


OperationNext = Callable[[OperationCall], Awaitable[Mapping[str, Any]]]


class OperationMiddleware(Protocol):
    async def invoke(
        self,
        call: OperationCall,
        next_handler: OperationNext,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class OperationExtensionBinding:
    """Validated runtime metadata associated with one middleware instance."""

    extension_id: str
    spi: str
    operations: frozenset[str]
    priority: int
    timeout_seconds: float
    middleware: OperationMiddleware

    def __post_init__(self) -> None:
        if not self.extension_id.strip():
            raise ValueError("extension_id must not be empty")
        if not self.spi.strip():
            raise ValueError("spi must not be empty")
        if not self.operations:
            raise ValueError(f"extension {self.extension_id!r} must select an operation")
        if self.timeout_seconds <= 0:
            raise ValueError(f"extension {self.extension_id!r} timeout must be positive")
        if not callable(getattr(self.middleware, "invoke", None)):
            raise TypeError(f"extension {self.extension_id!r} must implement async invoke")
