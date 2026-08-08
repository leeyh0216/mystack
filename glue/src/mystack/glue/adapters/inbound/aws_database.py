"""Glue database AWS operation family.

Official APIs: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-databases.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.glue.adapters.inbound.aws_context import GlueFamilyContext
from mystack.glue.adapters.inbound.aws_errors import glue_family
from mystack.glue.adapters.inbound.aws_shapes import (
    database_document,
    mapping,
    optional_int,
    optional_string,
    with_token,
)


class DatabaseOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return glue_family(
            "database",
            {
                "CreateDatabase": self.create_database,
                "DeleteDatabase": self.delete_database,
                "GetCatalogImportStatus": self.get_catalog_import_status,
                "GetDatabase": self.get_database,
                "GetDatabases": self.get_databases,
                "UpdateDatabase": self.update_database,
            },
        )

    async def create_database(self, payload, context):
        del context
        await self._context.application.create_database(
            self._context.catalog(payload),
            dict(mapping(payload["DatabaseInput"], "DatabaseInput")),
        )
        return {}

    async def get_database(self, payload, context):
        del context
        value = await self._context.application.get_database(
            self._context.catalog(payload), str(payload["Name"])
        )
        return {"Database": database_document(value)}

    async def get_databases(self, payload, context):
        del context
        values, token = await self._context.application.get_databases(
            self._context.catalog(payload),
            next_token=optional_string(payload.get("NextToken")),
            max_results=optional_int(payload.get("MaxResults")),
        )
        return with_token({"DatabaseList": [database_document(value) for value in values]}, token)

    async def update_database(self, payload, context):
        del context
        await self._context.application.update_database(
            self._context.catalog(payload),
            str(payload["Name"]),
            dict(mapping(payload["DatabaseInput"], "DatabaseInput")),
        )
        return {}

    async def delete_database(self, payload, context):
        del context
        await self._context.application.delete_database(
            self._context.catalog(payload), str(payload["Name"])
        )
        return {}

    async def get_catalog_import_status(self, payload, context):
        del payload, context
        return {
            "ImportStatus": {
                "ImportCompleted": True,
                "ImportTime": 0.0,
                "ImportedBy": "mystack",
            }
        }
