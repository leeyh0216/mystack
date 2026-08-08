"""Glue partial-success partition batch AWS operation family.

Official APIs:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily

from .aws_context import GlueFamilyContext
from .aws_errors import error_detail, glue_family
from .aws_shapes import mapping, partition_document, partition_error


class BatchOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return glue_family(
            "batch",
            {
                "BatchCreatePartition": self.batch_create_partition,
                "BatchDeletePartition": self.batch_delete_partition,
                "BatchGetPartition": self.batch_get_partition,
                "BatchUpdatePartition": self.batch_update_partition,
            },
        )

    async def batch_create_partition(self, payload, context):
        del context
        definitions = [
            dict(mapping(definition, "PartitionInput"))
            for definition in payload["PartitionInputList"]
        ]
        failures = await self._context.application.batch_create_partitions(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            definitions,
        )
        return {
            "Errors": [partition_error(list(failure.values), failure.error) for failure in failures]
        }

    async def batch_get_partition(self, payload, context):
        del context
        value_groups = [
            tuple(map(str, mapping(key, "PartitionsToGet[]")["Values"]))
            for key in payload["PartitionsToGet"]
        ]
        partitions = await self._context.application.batch_get_partitions(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            value_groups,
        )
        return {
            "Partitions": [partition_document(value) for value in partitions],
            "UnprocessedKeys": [],
        }

    async def batch_update_partition(self, payload, context):
        del context
        entries = []
        for entry in payload["Entries"]:
            item = mapping(entry, "Entries[]")
            entries.append(
                (
                    tuple(map(str, item["PartitionValueList"])),
                    dict(mapping(item["PartitionInput"], "PartitionInput")),
                )
            )
        failures = await self._context.application.batch_update_partitions(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            entries,
        )
        return {
            "Errors": [
                {
                    "PartitionValueList": list(failure.values),
                    "ErrorDetail": error_detail(failure.error),
                }
                for failure in failures
            ]
        }

    async def batch_delete_partition(self, payload, context):
        del context
        value_groups = [
            tuple(map(str, mapping(key, "PartitionsToDelete[]")["Values"]))
            for key in payload["PartitionsToDelete"]
        ]
        failures = await self._context.application.batch_delete_partitions(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            value_groups,
        )
        return {
            "Errors": [partition_error(list(failure.values), failure.error) for failure in failures]
        }
