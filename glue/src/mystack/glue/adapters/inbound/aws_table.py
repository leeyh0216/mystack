"""Glue table AWS operation family.

Official APIs: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-tables.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.glue.adapters.inbound.aws_context import GlueFamilyContext
from mystack.glue.adapters.inbound.aws_shapes import (
    attribute_keys,
    mapping,
    optional_int,
    optional_string,
    table_document,
    with_token,
)
from mystack.glue.domain import InvalidInputError


class TableOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return self._context.error_boundary.family(
            "table",
            {
                "CreateTable": self.create_table,
                "DeleteTable": self.delete_table,
                "GetTable": self.get_table,
                "GetTables": self.get_tables,
                "UpdateTable": self.update_table,
            },
        )

    async def create_table(self, payload, context):
        del context
        definition = payload.get("TableInput")
        if definition is None:
            raise InvalidInputError(
                "Mystack currently requires TableInput; OpenTableFormatInput is not implemented"
            )
        await self._context.application.create_table(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            dict(mapping(definition, "TableInput")),
        )
        return {}

    async def get_table(self, payload, context):
        del context
        value = await self._context.application.get_table(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["Name"]),
        )
        return {"Table": table_document(value)}

    async def get_tables(self, payload, context):
        del context
        values, token = await self._context.application.get_tables(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            expression=optional_string(payload.get("Expression")),
            next_token=optional_string(payload.get("NextToken")),
            max_results=optional_int(payload.get("MaxResults")),
        )
        attributes = set(map(str, payload.get("AttributesToGet", ())))
        tables = [table_document(value) for value in values]
        if attributes:
            allowed = attribute_keys(attributes)
            tables = [
                {key: value for key, value in table.items() if key in allowed} for table in tables
            ]
        return with_token({"TableList": tables}, token)

    async def update_table(self, payload, context):
        del context
        definition = payload.get("TableInput")
        if definition is None:
            raise InvalidInputError(
                "Mystack currently requires TableInput; "
                "UpdateOpenTableFormatInput is not implemented"
            )
        old_name = str(payload.get("Name") or mapping(definition, "TableInput")["Name"])
        await self._context.application.update_table(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            old_name,
            dict(mapping(definition, "TableInput")),
            version_id=optional_string(payload.get("VersionId")),
            skip_archive=bool(payload.get("SkipArchive", False)),
        )
        return {}

    async def delete_table(self, payload, context):
        del context
        await self._context.application.delete_table(
            self._context.catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["Name"]),
        )
        return {}
