"""EMR cluster-creation AWS operation family.

Official API: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.aws_protocol import AwsRequestContext, OperationFamily
from mystack.emr.application.use_cases import EmrClusterCommands

from .aws_errors import emr_family
from .aws_shapes import create_cluster_command


class ClusterOperationFamily:
    def __init__(self, commands: EmrClusterCommands) -> None:
        self._commands = commands

    def family(self) -> OperationFamily:
        return emr_family("cluster", {"RunJobFlow": self.run_job_flow})

    async def run_job_flow(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        command = create_cluster_command(payload)
        cluster = await self._commands.create_cluster(
            command,
            region=context.region,
            account_id=context.account_id,
        )
        return {"JobFlowId": cluster.id, "ClusterArn": cluster.arn}
