"""Exact-version, unsafe Glue extension SPI version 1.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mystack_aws_protocol import OperationMiddleware

from mystack_glue.application import CatalogApplication
from mystack_glue.application.ports import Clock
from mystack_glue.config import GlueSettings
from mystack_glue.domain.repositories import CatalogRepository

from ._common import GlueExtensionIdentity


@dataclass(frozen=True, slots=True)
class GlueUnsafeContextV1:
    identity: GlueExtensionIdentity
    application: CatalogApplication
    repository: CatalogRepository
    clock: Clock
    settings: GlueSettings
    mystack_version: str


class GlueUnsafeExtensionProviderV1(Protocol):
    def __call__(self, context: GlueUnsafeContextV1) -> OperationMiddleware: ...
