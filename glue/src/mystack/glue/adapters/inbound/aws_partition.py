"""Glue single-partition AWS operation family.

Official APIs:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily

from .aws_context import GlueFamilyContext
from .aws_errors import glue_family
from .aws_shapes import (
    mapping,
    optional_int,
    optional_string,
    partition_document,
    with_token,
    without_columns,
)


class PartitionOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return glue_family(
            "partition",
            {
                "CreatePartition": self.create_partition,
                "DeletePartition": self.delete_partition,
                "GetPartition": self.get_partition,
                "GetPartitions": self.get_partitions,
                "UpdatePartition": self.update_partition,
            },
        )

    async def create_partition(self, payload, context):
        del context
        await self._context.application.create_partition(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            dict(mapping(payload["PartitionInput"], "PartitionInput")),
        )
        return {}

    async def get_partition(self, payload, context):
        del context
        value = await self._context.application.get_partition(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValues"])),
        )
        return {"Partition": partition_document(value)}

    async def get_partitions(self, payload, context):
        del context
        raw_segment = payload.get("Segment")
        segment = None
        if raw_segment is not None:
            value = mapping(raw_segment, "Segment")
            segment = (int(value["SegmentNumber"]), int(value["TotalSegments"]))
        values, token = await self._context.application.get_partitions(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            expression=optional_string(payload.get("Expression")),
            segment=segment,
            next_token=optional_string(payload.get("NextToken")),
            max_results=optional_int(payload.get("MaxResults")),
        )
        partitions = [partition_document(value) for value in values]
        if payload.get("ExcludeColumnSchema"):
            partitions = [without_columns(value) for value in partitions]
        return with_token({"Partitions": partitions}, token)

    async def update_partition(self, payload, context):
        del context
        await self._context.application.update_partition(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValueList"])),
            dict(mapping(payload["PartitionInput"], "PartitionInput")),
        )
        return {}

    async def delete_partition(self, payload, context):
        del context
        await self._context.application.delete_partition(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValues"])),
        )
        return {}
