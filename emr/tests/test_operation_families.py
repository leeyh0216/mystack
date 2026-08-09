"""Isolated EMR inbound operation-family contracts.

Official inventory: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
"""

from __future__ import annotations

import pytest
from mystack.aws_protocol import AwsRequestContext, AwsServiceError
from mystack.emr.adapters.inbound.aws_cluster import ClusterOperationFamily
from mystack.emr.adapters.inbound.aws_control import ControlOperationFamily
from mystack.emr.adapters.inbound.aws_operations import IMPLEMENTED_EMR_OPERATIONS
from mystack.emr.adapters.inbound.aws_query import QueryOperationFamily
from mystack.emr.adapters.inbound.aws_step import StepOperationFamily
from mystack.emr.adapters.inbound.aws_tag import TagOperationFamily
from mystack.emr.domain.errors import InvalidClusterStateError

from scripts.api_coverage import IMPLEMENTED
from scripts.operation_inventory import extract_implemented_operation_inventory


class _FailingQueries:
    async def describe_cluster(self, cluster_id: str):
        raise InvalidClusterStateError(cluster_id)


def test_emr_families_are_disjoint_complete_and_match_coverage() -> None:
    dependency = object()
    families = (
        ClusterOperationFamily(dependency).family(),  # type: ignore[arg-type]
        StepOperationFamily(dependency).family(),  # type: ignore[arg-type]
        ControlOperationFamily(dependency).family(),  # type: ignore[arg-type]
        TagOperationFamily(dependency).family(),  # type: ignore[arg-type]
        QueryOperationFamily(dependency).family(),  # type: ignore[arg-type]
    )
    owners = [operation for family in families for operation in family.handlers]

    assert [family.name for family in families] == ["cluster", "step", "control", "tag", "query"]
    assert len(owners) == len(set(owners))
    extracted = extract_implemented_operation_inventory()
    assert set(owners) == IMPLEMENTED_EMR_OPERATIONS == extracted["emr"] == IMPLEMENTED["emr"]


@pytest.mark.asyncio
async def test_query_family_maps_errors_without_other_families() -> None:
    family = QueryOperationFamily(_FailingQueries()).family()  # type: ignore[arg-type]
    context = AwsRequestContext("request", "emr", "DescribeCluster", "us-east-1", "000000000000")

    with pytest.raises(AwsServiceError) as captured:
        await family.handlers["DescribeCluster"]({"ClusterId": "j-missing"}, context)

    assert captured.value.code == "InvalidRequestException"
    assert "query operation family" in str(captured.value.fix_hint)
