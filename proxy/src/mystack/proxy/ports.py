"""Typed capabilities exposed by the Proxy runtime to HTTP controllers.

Python structural subtyping reference:
https://docs.python.org/3/library/typing.html#typing.Protocol
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from fastapi.responses import Response

from .config import ServiceRoute


@dataclass(frozen=True, slots=True)
class RouteMatch:
    route: ServiceRoute | None
    evidence: str
    matched_value: str
    target_prefix: str
    signing_name: str
    host_prefix: str


class RouteDetector(Protocol):
    def detect(self, headers: Mapping[str, str]) -> RouteMatch: ...


class AwsRequestForwarding(Protocol):
    async def forward(self, request: Request) -> Response: ...


@dataclass(frozen=True, slots=True)
class ManagementResponse:
    content: bytes
    status_code: int
    content_type: str


class ManagementForwarding(Protocol):
    async def forward(
        self,
        *,
        component: str,
        backend_path: str,
        capability: str,
        authorization: str | None,
        query_params: Sequence[tuple[str, str]],
    ) -> ManagementResponse: ...


class UnknownManagementComponentError(LookupError):
    """The component name has no configured management backend."""


class ManagementBackendUnavailableError(RuntimeError):
    """The configured component did not return an HTTP response."""
