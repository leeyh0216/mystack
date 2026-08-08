"""EMR read-only AWS operation family.

Official APIs:
https://docs.aws.amazon.com/emr/latest/APIReference/API_DescribeCluster.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_ListClusters.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_ListSteps.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.emr.application.use_cases import EmrQueries
from mystack.emr.domain import ClusterState, StepState

from .aws_errors import emr_family
from .aws_shapes import (
    cluster_document,
    cluster_summary,
    optional_float,
    optional_string,
    step_document,
    with_marker,
)


class QueryOperationFamily:
    def __init__(self, queries: EmrQueries) -> None:
        self._queries = queries

    def family(self) -> OperationFamily:
        return emr_family(
            "query",
            {
                "DescribeCluster": self.describe_cluster,
                "DescribeStep": self.describe_step,
                "ListBootstrapActions": self.list_bootstrap_actions,
                "ListClusters": self.list_clusters,
                "ListSteps": self.list_steps,
            },
        )

    async def describe_cluster(self, payload, context):
        del context
        cluster = await self._queries.describe_cluster(str(payload["ClusterId"]))
        return {"Cluster": cluster_document(cluster)}

    async def describe_step(self, payload, context):
        del context
        step = await self._queries.describe_step(str(payload["ClusterId"]), str(payload["StepId"]))
        return {"Step": step_document(step)}

    async def list_clusters(self, payload, context):
        del context
        states = (
            {ClusterState(str(value)) for value in payload["ClusterStates"]}
            if payload.get("ClusterStates")
            else None
        )
        clusters, marker = await self._queries.list_clusters(
            states=states,
            created_after=optional_float(payload.get("CreatedAfter")),
            created_before=optional_float(payload.get("CreatedBefore")),
            marker=optional_string(payload.get("Marker")),
        )
        return with_marker({"Clusters": [cluster_summary(value) for value in clusters]}, marker)

    async def list_steps(self, payload, context):
        del context
        states = (
            {StepState(str(value)) for value in payload["StepStates"]}
            if payload.get("StepStates")
            else None
        )
        step_ids = set(map(str, payload["StepIds"])) if payload.get("StepIds") else None
        steps, marker = await self._queries.list_steps(
            str(payload["ClusterId"]),
            states=states,
            step_ids=step_ids,
            marker=optional_string(payload.get("Marker")),
        )
        return with_marker({"Steps": [step_document(value) for value in steps]}, marker)

    async def list_bootstrap_actions(self, payload, context):
        del context
        actions, marker = await self._queries.list_bootstrap_actions(
            str(payload["ClusterId"]), marker=optional_string(payload.get("Marker"))
        )
        result = {
            "BootstrapActions": [
                {"Name": value.name, "ScriptPath": value.path, "Args": list(value.args)}
                for value in actions
            ]
        }
        return with_marker(result, marker)
