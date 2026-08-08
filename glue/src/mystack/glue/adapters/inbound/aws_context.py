"""Shared immutable context passed to Glue operation families.

CatalogId behavior: https://docs.aws.amazon.com/glue/latest/webapi/API_GetDatabase.html
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mystack.glue.adapters.inbound.aws_errors import GlueErrorBoundary
from mystack.glue.application.use_cases import GlueCatalogUseCases


@dataclass(frozen=True, slots=True)
class GlueFamilyContext:
    application: GlueCatalogUseCases
    default_catalog_id: str
    error_boundary: GlueErrorBoundary

    def catalog(self, payload: Mapping[str, Any]) -> str:
        return str(payload.get("CatalogId", self.default_catalog_id))
