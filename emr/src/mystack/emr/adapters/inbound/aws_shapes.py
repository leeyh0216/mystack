"""EMR AWS request and response shape translation helpers.

Official shapes:
https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_Cluster.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_Step.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.emr.domain import (
    ActionOnFailure,
    BootstrapAction,
    Cluster,
    SparkStepConfig,
    Step,
    StepSpec,
)


def step_spec(raw: object) -> StepSpec:
    value = mapping(raw, "Steps[]")
    hadoop = mapping(value["HadoopJarStep"], "Steps[].HadoopJarStep")
    return StepSpec(
        name=str(value["Name"]),
        action_on_failure=ActionOnFailure(str(value.get("ActionOnFailure", "TERMINATE_CLUSTER"))),
        config=SparkStepConfig(
            jar=str(hadoop["Jar"]),
            args=tuple(map(str, hadoop.get("Args", ()))),
            main_class=optional_string(hadoop.get("MainClass")),
            properties=tuple(property_pair(item) for item in hadoop.get("Properties", ())),
        ),
    )


def bootstrap(raw: object) -> BootstrapAction:
    value = mapping(raw, "BootstrapActions[]")
    script = mapping(value["ScriptBootstrapAction"], "ScriptBootstrapAction")
    return BootstrapAction(
        name=str(value["Name"]),
        path=str(script["Path"]),
        args=tuple(map(str, script.get("Args", ()))),
    )


def cluster_document(cluster: Cluster) -> dict[str, Any]:
    result = cluster_summary(cluster)
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


def cluster_summary(cluster: Cluster) -> dict[str, Any]:
    return {
        "Id": cluster.id,
        "Name": cluster.name,
        "Status": _cluster_status(cluster),
        "NormalizedInstanceHours": 0,
        "ClusterArn": cluster.arn,
    }


def step_document(step: Step) -> dict[str, Any]:
    status: dict[str, Any] = {
        "State": step.state.value,
        "StateChangeReason": _step_state_reason(step.reason.code, step.reason.message),
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


def resource_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("ResourceId") or payload.get("ClusterId")
    if value is None:
        raise ValueError("ResourceId or ClusterId is required")
    return str(value)


def mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    return value


def tag(value: object) -> tuple[str, str]:
    document = mapping(value, "Tags[]")
    return str(document["Key"]), str(document["Value"])


def property_pair(value: object) -> tuple[str, str]:
    document = mapping(value, "Properties[]")
    return str(document["Key"]), str(document["Value"])


def optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def with_marker(result: dict[str, Any], marker: str | None) -> dict[str, Any]:
    if marker is not None:
        result["Marker"] = marker
    return result


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


def _ec2_attributes(instances: Mapping[str, Any]) -> dict[str, Any]:
    names = {
        "Ec2KeyName",
        "Ec2SubnetId",
        "EmrManagedMasterSecurityGroup",
        "EmrManagedSlaveSecurityGroup",
        "ServiceAccessSecurityGroup",
        "AdditionalMasterSecurityGroups",
        "AdditionalSlaveSecurityGroups",
    }
    result = {name: instances[name] for name in names if name in instances}
    placement = instances.get("Placement")
    if isinstance(placement, Mapping) and placement.get("AvailabilityZone"):
        result["Ec2AvailabilityZone"] = placement["AvailabilityZone"]
    return result


def _state_reason(code: str, message: str) -> dict[str, str]:
    return {key: value for key, value in (("Code", code), ("Message", message)) if value}


def _step_state_reason(code: str, message: str) -> dict[str, str]:
    # Official enum currently permits only NONE. Rich internal reasons remain in logs.
    # https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStateChangeReason.html
    return _state_reason("NONE" if code else "", message)
