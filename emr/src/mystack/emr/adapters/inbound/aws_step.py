"""EMR Step command AWS operation family.

Official APIs:
https://docs.aws.amazon.com/emr/latest/APIReference/API_AddJobFlowSteps.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_CancelSteps.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.aws_protocol import AwsRequestContext, OperationFamily
from mystack.emr.adapters.inbound.aws_errors import emr_family
from mystack.emr.adapters.inbound.aws_shapes import step_spec
from mystack.emr.application.commands import AddSteps
from mystack.emr.application.use_cases import EmrStepCommands


class StepOperationFamily:
    def __init__(self, commands: EmrStepCommands) -> None:
        self._commands = commands

    def family(self) -> OperationFamily:
        return emr_family(
            "step",
            {
                "AddJobFlowSteps": self.add_job_flow_steps,
                "CancelSteps": self.cancel_steps,
            },
        )

    async def add_job_flow_steps(self, payload, context):
        del context
        steps = await self._commands.add_steps(
            AddSteps(
                cluster_id=str(payload["JobFlowId"]),
                steps=tuple(step_spec(value) for value in payload["Steps"]),
            )
        )
        return {"StepIds": [step.id for step in steps]}

    async def cancel_steps(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        results = await self._commands.cancel_steps(
            str(payload["ClusterId"]), map(str, payload["StepIds"])
        )
        return {
            "CancelStepsInfoList": [
                {"StepId": step_id, "Status": status} for step_id, status in results.items()
            ]
        }
