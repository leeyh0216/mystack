"""EMR lifecycle-control AWS operation family.

Official APIs:
https://docs.aws.amazon.com/emr/latest/APIReference/API_TerminateJobFlows.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_SetTerminationProtection.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.emr.application.use_cases import EmrClusterCommands

from .aws_errors import emr_family


class ControlOperationFamily:
    def __init__(self, commands: EmrClusterCommands) -> None:
        self._commands = commands

    def family(self) -> OperationFamily:
        return emr_family(
            "control",
            {
                "SetTerminationProtection": self.set_termination_protection,
                "SetVisibleToAllUsers": self.set_visible_to_all_users,
                "TerminateJobFlows": self.terminate_job_flows,
            },
        )

    async def terminate_job_flows(self, payload, context):
        del context
        await self._commands.terminate_clusters(map(str, payload["JobFlowIds"]))
        return {}

    async def set_termination_protection(self, payload, context):
        del context
        await self._commands.set_termination_protection(
            map(str, payload["JobFlowIds"]), bool(payload["TerminationProtected"])
        )
        return {}

    async def set_visible_to_all_users(self, payload, context):
        del context
        await self._commands.set_visible_to_all_users(
            map(str, payload["JobFlowIds"]), bool(payload["VisibleToAllUsers"])
        )
        return {}
