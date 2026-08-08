"""Application-level Glue extension SPI version 1.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mystack_aws_protocol import OperationMiddleware

from mystack_glue.application import CatalogApplication

from ._common import GlueExtensionIdentity


@dataclass(frozen=True, slots=True)
class GlueApplicationContextV1:
    identity: GlueExtensionIdentity
    application: CatalogApplication
    default_catalog_id: str
    mystack_version: str


class GlueApplicationExtensionProviderV1(Protocol):
    def __call__(self, context: GlueApplicationContextV1) -> OperationMiddleware: ...
