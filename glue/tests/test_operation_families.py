"""Isolated Glue inbound operation-family contracts.

Official inventory: https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
"""

from __future__ import annotations

import pytest
from mystack.aws_protocol import AwsRequestContext, AwsServiceError
from mystack.glue.adapters.inbound.aws_batch import BatchOperationFamily
from mystack.glue.adapters.inbound.aws_context import GlueFamilyContext
from mystack.glue.adapters.inbound.aws_database import DatabaseOperationFamily
from mystack.glue.adapters.inbound.aws_errors import GlueErrorBoundary, GlueErrorTranslator
from mystack.glue.adapters.inbound.aws_faults import GlueFaultInjector
from mystack.glue.adapters.inbound.aws_operations import IMPLEMENTED_GLUE_OPERATIONS
from mystack.glue.adapters.inbound.aws_optimizer import TableOptimizerOperationFamily
from mystack.glue.adapters.inbound.aws_partition import PartitionOperationFamily
from mystack.glue.adapters.inbound.aws_table import TableOperationFamily
from mystack.glue.adapters.inbound.aws_version import VersionOperationFamily
from mystack.glue.application.policies import GlueFaultInjectionPolicy
from mystack.glue.domain import AlreadyExistsError

from scripts.compatibility.api_coverage import IMPLEMENTED
from scripts.compatibility.operation_inventory import extract_implemented_operation_inventory


class _FailingDatabaseCommands:
    async def create_database(self, catalog_id: str, definition: dict):
        del catalog_id, definition
        raise AlreadyExistsError("database exists")


def test_glue_families_are_disjoint_complete_and_match_coverage() -> None:
    context = GlueFamilyContext(
        object(),  # type: ignore[arg-type]
        "000000000000",
        _error_boundary(),
    )
    families = (
        DatabaseOperationFamily(context).family(),
        TableOperationFamily(context).family(),
        VersionOperationFamily(context).family(),
        PartitionOperationFamily(context).family(),
        BatchOperationFamily(context).family(),
        TableOptimizerOperationFamily(context).family(),
    )
    owners = [operation for family in families for operation in family.handlers]

    assert [family.name for family in families] == [
        "database",
        "table",
        "version",
        "partition",
        "batch",
        "table-optimizer",
    ]
    assert len(owners) == len(set(owners))
    extracted = extract_implemented_operation_inventory()
    assert set(owners) == IMPLEMENTED_GLUE_OPERATIONS == extracted["glue"] == IMPLEMENTED["glue"]


@pytest.mark.asyncio
async def test_database_family_maps_modeled_error_without_other_families() -> None:
    family_context = GlueFamilyContext(
        _FailingDatabaseCommands(),  # type: ignore[arg-type]
        "000000000000",
        _error_boundary(),
    )
    family = DatabaseOperationFamily(family_context).family()
    context = AwsRequestContext("request", "glue", "CreateDatabase", "us-east-1", "000000000000")

    with pytest.raises(AwsServiceError) as captured:
        await family.handlers["CreateDatabase"]({"DatabaseInput": {"Name": "existing"}}, context)

    assert captured.value.code == "AlreadyExistsException"
    assert "database operation family" in str(captured.value.fix_hint)


def _error_boundary() -> GlueErrorBoundary:
    return GlueErrorBoundary(
        GlueErrorTranslator(),
        GlueFaultInjector(GlueFaultInjectionPolicy.disabled(), IMPLEMENTED_GLUE_OPERATIONS),
    )
