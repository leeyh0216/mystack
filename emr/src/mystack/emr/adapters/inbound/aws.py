"""Compose EMR AWS JSON 1.1 operation families into one validated dispatcher.

Official API inventory: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationDispatcher, OperationFamilyRegistry
from mystack.emr.adapters.inbound.aws_cluster import ClusterOperationFamily
from mystack.emr.adapters.inbound.aws_control import ControlOperationFamily
from mystack.emr.adapters.inbound.aws_operations import IMPLEMENTED_EMR_OPERATIONS
from mystack.emr.adapters.inbound.aws_query import QueryOperationFamily
from mystack.emr.adapters.inbound.aws_step import StepOperationFamily
from mystack.emr.adapters.inbound.aws_tag import TagOperationFamily
from mystack.emr.application.use_cases import EmrClusterCommands, EmrQueries, EmrStepCommands


class EmrAwsAdapter:
    """Composition-only adapter; operation behavior lives in focused family classes."""

    def __init__(
        self,
        cluster_commands: EmrClusterCommands,
        step_commands: EmrStepCommands,
        queries: EmrQueries,
    ) -> None:
        self._families = (
            ClusterOperationFamily(cluster_commands).family(),
            StepOperationFamily(step_commands).family(),
            ControlOperationFamily(cluster_commands).family(),
            TagOperationFamily(cluster_commands).family(),
            QueryOperationFamily(queries).family(),
        )

    def dispatcher(self) -> OperationDispatcher:
        return OperationFamilyRegistry("emr", IMPLEMENTED_EMR_OPERATIONS).dispatcher(self._families)
