"""Glue table-version AWS operation family.

Official APIs: https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily

from .aws_context import GlueFamilyContext
from .aws_errors import glue_family
from .aws_shapes import optional_int, optional_string, table_version_document, with_token


class VersionOperationFamily:
    def __init__(self, context: GlueFamilyContext) -> None:
        self._context = context

    def family(self) -> OperationFamily:
        return glue_family(
            "version",
            {
                "GetTableVersion": self.get_table_version,
                "GetTableVersions": self.get_table_versions,
            },
        )

    async def get_table_version(self, payload, context):
        del context
        catalog_id = self._context.catalog(payload)
        database = str(payload["DatabaseName"])
        value = await self._context.application.get_table_version(
            catalog_id,
            database,
            str(payload["TableName"]),
            optional_string(payload.get("VersionId")),
        )
        return {"TableVersion": table_version_document(value, catalog_id, database)}

    async def get_table_versions(self, payload, context):
        del context
        catalog_id = self._context.catalog(payload)
        database = str(payload["DatabaseName"])
        values, token = await self._context.application.get_table_versions(
            catalog_id,
            database,
            str(payload["TableName"]),
            next_token=optional_string(payload.get("NextToken")),
            max_results=optional_int(payload.get("MaxResults")),
        )
        result = {
            "TableVersions": [
                table_version_document(value, catalog_id, database) for value in values
            ]
        }
        return with_token(result, token)
