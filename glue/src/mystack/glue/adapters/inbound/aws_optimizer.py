"""Glue managed Iceberg table-optimizer AWS JSON operation family.

Official API: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.glue.adapters.inbound.aws_context import GlueFamilyContext
from mystack.glue.adapters.inbound.aws_shapes import (
    mapping,
    optional_int,
    optional_string,
    table_optimizer_document,
    table_optimizer_run_document,
    with_token,
)


class TableOptimizerOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return self._context.error_boundary.family(
            "table-optimizer",
            {
                "BatchGetTableOptimizer": self.batch_get_table_optimizer,
                "CreateTableOptimizer": self.create_table_optimizer,
                "DeleteTableOptimizer": self.delete_table_optimizer,
                "GetTableOptimizer": self.get_table_optimizer,
                "ListTableOptimizerRuns": self.list_table_optimizer_runs,
                "UpdateTableOptimizer": self.update_table_optimizer,
            },
        )

    async def create_table_optimizer(self, payload, context):
        del context
        await self._context.application.create_table_optimizer(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            payload["Type"],
            dict(mapping(payload["TableOptimizerConfiguration"], "TableOptimizerConfiguration")),
        )
        return {}

    async def update_table_optimizer(self, payload, context):
        del context
        await self._context.application.update_table_optimizer(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            payload["Type"],
            dict(mapping(payload["TableOptimizerConfiguration"], "TableOptimizerConfiguration")),
        )
        return {}

    async def delete_table_optimizer(self, payload, context):
        del context
        await self._context.application.delete_table_optimizer(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            payload["Type"],
        )
        return {}

    async def get_table_optimizer(self, payload, context):
        del context
        catalog_id = self._context.catalog(payload)
        database_name = str(payload["DatabaseName"])
        table_name = str(payload["TableName"])
        value = await self._context.application.get_table_optimizer(
            catalog_id,
            database_name,
            table_name,
            payload["Type"],
        )
        return {
            "CatalogId": value.catalog_id,
            "DatabaseName": value.database_name,
            "TableName": value.table_name,
            "TableOptimizer": table_optimizer_document(value),
        }

    async def batch_get_table_optimizer(self, payload, context):
        del context
        entries = []
        for raw in payload["Entries"]:
            entry = mapping(raw, "Entries[]")
            entries.append(
                (
                    str(entry.get("catalogId", self._context.default_catalog_id)),
                    str(entry.get("databaseName", "")),
                    str(entry.get("tableName", "")),
                    entry.get("type", ""),
                )
            )
        result = await self._context.application.batch_get_table_optimizers(entries)
        return {
            "TableOptimizers": [
                {
                    "catalogId": value.catalog_id,
                    "databaseName": value.database_name,
                    "tableName": value.table_name,
                    "tableOptimizer": table_optimizer_document(value),
                }
                for value in result.optimizers
            ],
            "Failures": [
                {
                    "catalogId": failure.catalog_id,
                    "databaseName": failure.database_name,
                    "tableName": failure.table_name,
                    "type": failure.optimizer_type,
                    "error": self._context.error_boundary.error_detail(failure.error),
                }
                for failure in result.failures
            ],
        }

    async def list_table_optimizer_runs(self, payload, context):
        del context
        catalog_id = self._context.catalog(payload)
        database_name = str(payload["DatabaseName"])
        table_name = str(payload["TableName"])
        values, token = await self._context.application.list_table_optimizer_runs(
            catalog_id,
            database_name,
            table_name,
            payload["Type"],
            next_token=optional_string(payload.get("NextToken")),
            max_results=optional_int(payload.get("MaxResults")),
        )
        return with_token(
            {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "TableName": table_name,
                "TableOptimizerRuns": [
                    table_optimizer_run_document(run, payload["Type"]) for run in values
                ],
            },
            token,
        )
