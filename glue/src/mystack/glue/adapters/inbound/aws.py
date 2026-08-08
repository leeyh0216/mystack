"""Compose Glue AWS JSON 1.1 operation families into one validated dispatcher.

Official API inventory: https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationDispatcher, OperationFamilyRegistry
from mystack.glue.adapters.inbound.aws_batch import BatchOperationFamily
from mystack.glue.adapters.inbound.aws_context import GlueFamilyContext
from mystack.glue.adapters.inbound.aws_database import DatabaseOperationFamily
from mystack.glue.adapters.inbound.aws_operations import IMPLEMENTED_GLUE_OPERATIONS
from mystack.glue.adapters.inbound.aws_partition import PartitionOperationFamily
from mystack.glue.adapters.inbound.aws_table import TableOperationFamily
from mystack.glue.adapters.inbound.aws_version import VersionOperationFamily
from mystack.glue.application.use_cases import GlueCatalogUseCases


class GlueAwsAdapter:
    """Composition-only adapter; operation behavior lives in focused family classes."""

    def __init__(self, application: GlueCatalogUseCases, default_catalog_id: str) -> None:
        context = GlueFamilyContext(application, default_catalog_id)
        self._families = (
            DatabaseOperationFamily(context).family(),
            TableOperationFamily(context).family(),
            VersionOperationFamily(context).family(),
            PartitionOperationFamily(context).family(),
            BatchOperationFamily(context).family(),
        )

    def dispatcher(self) -> OperationDispatcher:
        return OperationFamilyRegistry("glue", IMPLEMENTED_GLUE_OPERATIONS).dispatcher(
            self._families
        )
