"""EMR cluster-creation AWS operation family.

Official API: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.aws_protocol import AwsRequestContext, OperationFamily
from mystack.emr.application.commands import CreateCluster
from mystack.emr.application.use_cases import EmrClusterCommands

from .aws_errors import emr_family
from .aws_shapes import bootstrap, mapping, optional_string, step_spec, tag


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
        instances = mapping(payload["Instances"], "Instances")
        command = CreateCluster(
            name=str(payload["Name"]),
            instance_config=dict(instances),
            release_label=optional_string(payload.get("ReleaseLabel")),
            keep_alive=bool(instances.get("KeepJobFlowAliveWhenNoSteps", False)),
            termination_protected=bool(instances.get("TerminationProtected", False)),
            visible_to_all_users=bool(payload.get("VisibleToAllUsers", True)),
            step_concurrency_level=int(payload.get("StepConcurrencyLevel", 1)),
            applications=tuple(
                dict(mapping(value, "Applications[]")) for value in payload.get("Applications", ())
            ),
            bootstrap_actions=tuple(
                bootstrap(value) for value in payload.get("BootstrapActions", ())
            ),
            steps=tuple(step_spec(value) for value in payload.get("Steps", ())),
            tags=tuple(tag(value) for value in payload.get("Tags", ())),
            log_uri=optional_string(payload.get("LogUri")),
            service_role=optional_string(payload.get("ServiceRole")),
        )
        cluster = await self._commands.create_cluster(
            command,
            region=context.region,
            account_id=context.account_id,
        )
        return {"JobFlowId": cluster.id, "ClusterArn": cluster.arn}
