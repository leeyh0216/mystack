"""Translate official EMR AWS JSON 1.1 operations to application use cases.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_InvalidRequestException.html
- https://github.com/boto/botocore/tree/develop/botocore/data/emr
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from mystack_aws_protocol import AwsRequestContext, AwsServiceError, OperationDispatcher

from mystack_emr.application import EmrApplication
from mystack_emr.application.commands import AddSteps, CreateCluster
from mystack_emr.domain import (
    ActionOnFailure,
    BootstrapAction,
    Cluster,
    ClusterState,
    SparkStepConfig,
    Step,
    StepSpec,
    StepState,
)
from mystack_emr.domain.errors import EmrDomainError

Handler = Callable[[Mapping[str, Any], AwsRequestContext], Awaitable[Mapping[str, Any]]]


class EmrAwsAdapter:
    """Explicit operation mapping; this is the sole AWS-to-domain translation boundary."""

    def __init__(self, application: EmrApplication) -> None:
        self._application = application

    def dispatcher(self) -> OperationDispatcher:
        operations: dict[str, Handler] = {
            "AddJobFlowSteps": self.add_job_flow_steps,
            "AddTags": self.add_tags,
            "CancelSteps": self.cancel_steps,
            "DescribeCluster": self.describe_cluster,
            "DescribeStep": self.describe_step,
            "ListBootstrapActions": self.list_bootstrap_actions,
            "ListClusters": self.list_clusters,
            "ListSteps": self.list_steps,
            "RemoveTags": self.remove_tags,
            "RunJobFlow": self.run_job_flow,
            "SetTerminationProtection": self.set_termination_protection,
            "SetVisibleToAllUsers": self.set_visible_to_all_users,
            "TerminateJobFlows": self.terminate_job_flows,
        }
        return OperationDispatcher(
            {name: self._translate_domain_errors(handler) for name, handler in operations.items()}
        )

    async def run_job_flow(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        instances = _mapping(payload["Instances"], "Instances")
        command = CreateCluster(
            name=str(payload["Name"]),
            instance_config=dict(instances),
            release_label=_optional_string(payload.get("ReleaseLabel")),
            keep_alive=bool(instances.get("KeepJobFlowAliveWhenNoSteps", False)),
            termination_protected=bool(instances.get("TerminationProtected", False)),
            visible_to_all_users=bool(payload.get("VisibleToAllUsers", True)),
            step_concurrency_level=int(payload.get("StepConcurrencyLevel", 1)),
            applications=tuple(
                dict(_mapping(value, "Applications[]")) for value in payload.get("Applications", ())
            ),
            bootstrap_actions=tuple(
                _bootstrap(value) for value in payload.get("BootstrapActions", ())
            ),
            steps=tuple(_step_spec(value) for value in payload.get("Steps", ())),
            tags=tuple(_tag(value) for value in payload.get("Tags", ())),
            log_uri=_optional_string(payload.get("LogUri")),
            service_role=_optional_string(payload.get("ServiceRole")),
        )
        cluster = await self._application.create_cluster(
            command,
            region=context.region,
            account_id=context.account_id,
        )
        return {"JobFlowId": cluster.id, "ClusterArn": cluster.arn}

    async def describe_cluster(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        cluster = await self._application.describe_cluster(str(payload["ClusterId"]))
        return {"Cluster": _cluster(cluster)}

    async def list_clusters(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        states = (
            {ClusterState(str(value)) for value in payload["ClusterStates"]}
            if payload.get("ClusterStates")
            else None
        )
        clusters, marker = await self._application.list_clusters(
            states=states,
            created_after=_optional_float(payload.get("CreatedAfter")),
            created_before=_optional_float(payload.get("CreatedBefore")),
            marker=_optional_string(payload.get("Marker")),
        )
        return _with_marker({"Clusters": [_cluster_summary(value) for value in clusters]}, marker)

    async def add_job_flow_steps(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        command = AddSteps(
            cluster_id=str(payload["JobFlowId"]),
            steps=tuple(_step_spec(value) for value in payload["Steps"]),
        )
        steps = await self._application.add_steps(command)
        return {"StepIds": [step.id for step in steps]}

    async def describe_step(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        step = await self._application.describe_step(
            str(payload["ClusterId"]),
            str(payload["StepId"]),
        )
        return {"Step": _step(step)}

    async def list_steps(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        states = (
            {StepState(str(value)) for value in payload["StepStates"]}
            if payload.get("StepStates")
            else None
        )
        step_ids = set(map(str, payload["StepIds"])) if payload.get("StepIds") else None
        steps, marker = await self._application.list_steps(
            str(payload["ClusterId"]),
            states=states,
            step_ids=step_ids,
            marker=_optional_string(payload.get("Marker")),
        )
        return _with_marker({"Steps": [_step(value) for value in steps]}, marker)

    async def cancel_steps(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        results = await self._application.cancel_steps(
            str(payload["ClusterId"]),
            map(str, payload["StepIds"]),
        )
        return {
            "CancelStepsInfoList": [
                {"StepId": step_id, "Status": status} for step_id, status in results.items()
            ]
        }

    async def terminate_job_flows(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        await self._application.terminate_clusters(map(str, payload["JobFlowIds"]))
        return {}

    async def list_bootstrap_actions(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        actions, marker = await self._application.list_bootstrap_actions(
            str(payload["ClusterId"]),
            marker=_optional_string(payload.get("Marker")),
        )
        result = {
            "BootstrapActions": [
                {"Name": value.name, "ScriptPath": value.path, "Args": list(value.args)}
                for value in actions
            ]
        }
        return _with_marker(result, marker)

    async def add_tags(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        await self._application.add_tags(
            _resource_id(payload),
            dict(_tag(value) for value in payload["Tags"]),
        )
        return {}

    async def remove_tags(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        await self._application.remove_tags(_resource_id(payload), map(str, payload["TagKeys"]))
        return {}

    async def set_termination_protection(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        await self._application.set_termination_protection(
            map(str, payload["JobFlowIds"]),
            bool(payload["TerminationProtected"]),
        )
        return {}

    async def set_visible_to_all_users(
        self,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        del context
        await self._application.set_visible_to_all_users(
            map(str, payload["JobFlowIds"]),
            bool(payload["VisibleToAllUsers"]),
        )
        return {}

    def _translate_domain_errors(self, handler: Handler) -> Handler:
        async def translated(
            payload: Mapping[str, Any],
            context: AwsRequestContext,
        ) -> Mapping[str, Any]:
            try:
                return await handler(payload, context)
            except (EmrDomainError, KeyError, TypeError, ValueError) as error:
                raise AwsServiceError(
                    "InvalidRequestException",
                    str(error),
                    http_status=400,
                    fix_hint=(
                        "Check the operation mapper in mystack_emr/adapters/inbound/aws.py "
                        "against the pinned EMR model and AWS API Reference."
                    ),
                ) from error

        return translated


def _step_spec(raw: object) -> StepSpec:
    value = _mapping(raw, "Steps[]")
    hadoop = _mapping(value["HadoopJarStep"], "Steps[].HadoopJarStep")
    return StepSpec(
        name=str(value["Name"]),
        action_on_failure=ActionOnFailure(str(value.get("ActionOnFailure", "TERMINATE_CLUSTER"))),
        config=SparkStepConfig(
            jar=str(hadoop["Jar"]),
            args=tuple(map(str, hadoop.get("Args", ()))),
            main_class=_optional_string(hadoop.get("MainClass")),
            properties=tuple(_property(item) for item in hadoop.get("Properties", ())),
        ),
    )


def _bootstrap(raw: object) -> BootstrapAction:
    value = _mapping(raw, "BootstrapActions[]")
    script = _mapping(value["ScriptBootstrapAction"], "ScriptBootstrapAction")
    return BootstrapAction(
        name=str(value["Name"]),
        path=str(script["Path"]),
        args=tuple(map(str, script.get("Args", ()))),
    )


def _cluster(cluster: Cluster) -> dict[str, Any]:
    result = _cluster_summary(cluster)
    result.update(
        {
            "ReleaseLabel": cluster.release_label,
            "AutoTerminate": not cluster.keep_alive,
            "TerminationProtected": cluster.termination_protected,
            "VisibleToAllUsers": cluster.visible_to_all_users,
            "Applications": list(cluster.applications),
            "Tags": [{"Key": key, "Value": value} for key, value in cluster.tags.items()],
            "StepConcurrencyLevel": cluster.step_concurrency_level,
            "InstanceCollectionType": (
                "INSTANCE_FLEET"
                if cluster.instance_config.get("InstanceFleets")
                else "INSTANCE_GROUP"
            ),
            "Ec2InstanceAttributes": _ec2_attributes(cluster.instance_config),
        }
    )
    if cluster.log_uri is not None:
        result["LogUri"] = cluster.log_uri
    if cluster.service_role is not None:
        result["ServiceRole"] = cluster.service_role
    return result


def _cluster_summary(cluster: Cluster) -> dict[str, Any]:
    return {
        "Id": cluster.id,
        "Name": cluster.name,
        "Status": _cluster_status(cluster),
        "NormalizedInstanceHours": 0,
        "ClusterArn": cluster.arn,
    }


def _cluster_status(cluster: Cluster) -> dict[str, Any]:
    timeline: dict[str, Any] = {"CreationDateTime": cluster.timeline.creation}
    if cluster.timeline.ready is not None:
        timeline["ReadyDateTime"] = cluster.timeline.ready
    if cluster.timeline.end is not None:
        timeline["EndDateTime"] = cluster.timeline.end
    return {
        "State": cluster.state.value,
        "StateChangeReason": _state_reason(cluster.reason.code, cluster.reason.message),
        "Timeline": timeline,
    }


def _step(step: Step) -> dict[str, Any]:
    status: dict[str, Any] = {
        "State": step.state.value,
        "StateChangeReason": _state_reason(step.reason.code, step.reason.message),
        "Timeline": {"CreationDateTime": step.timeline.creation},
    }
    if step.timeline.start is not None:
        status["Timeline"]["StartDateTime"] = step.timeline.start
    if step.timeline.end is not None:
        status["Timeline"]["EndDateTime"] = step.timeline.end
    if step.failure_details is not None:
        status["FailureDetails"] = step.failure_details
    config: dict[str, Any] = {
        "Jar": step.config.jar,
        "Properties": dict(step.config.properties),
        "Args": list(step.config.args),
    }
    if step.config.main_class is not None:
        config["MainClass"] = step.config.main_class
    return {
        "Id": step.id,
        "Name": step.name,
        "Config": config,
        "ActionOnFailure": step.action_on_failure.value,
        "Status": status,
    }


def _ec2_attributes(instances: Mapping[str, Any]) -> dict[str, Any]:
    mapping = {
        "Ec2KeyName": "Ec2KeyName",
        "Ec2SubnetId": "Ec2SubnetId",
        "EmrManagedMasterSecurityGroup": "EmrManagedMasterSecurityGroup",
        "EmrManagedSlaveSecurityGroup": "EmrManagedSlaveSecurityGroup",
        "ServiceAccessSecurityGroup": "ServiceAccessSecurityGroup",
        "AdditionalMasterSecurityGroups": "AdditionalMasterSecurityGroups",
        "AdditionalSlaveSecurityGroups": "AdditionalSlaveSecurityGroups",
    }
    result = {
        output: instances[source] for source, output in mapping.items() if source in instances
    }
    placement = instances.get("Placement")
    if isinstance(placement, Mapping) and placement.get("AvailabilityZone"):
        result["Ec2AvailabilityZone"] = placement["AvailabilityZone"]
    return result


def _state_reason(code: str, message: str) -> dict[str, str]:
    return {key: value for key, value in (("Code", code), ("Message", message)) if value}


def _resource_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("ResourceId") or payload.get("ClusterId")
    if value is None:
        raise ValueError("ResourceId or ClusterId is required")
    return str(value)


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    return value


def _tag(value: object) -> tuple[str, str]:
    tag = _mapping(value, "Tags[]")
    return str(tag["Key"]), str(tag["Value"])


def _property(value: object) -> tuple[str, str]:
    prop = _mapping(value, "Properties[]")
    return str(prop["Key"]), str(prop["Value"])


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _with_marker(result: dict[str, Any], marker: str | None) -> dict[str, Any]:
    if marker is not None:
        result["Marker"] = marker
    return result
