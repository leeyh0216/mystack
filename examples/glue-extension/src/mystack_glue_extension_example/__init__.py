"""Example Glue error translation using all three extension SPI contexts.

AWS error contract:
https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html

Python entry-point discovery:
https://docs.python.org/3/library/importlib.metadata.html#entry-points
"""

from __future__ import annotations

from typing import Any

from mystack_aws_protocol import AwsServiceError, OperationCall, OperationNext
from mystack_glue.extension_api import (
    GlueApplicationContextV1,
    GlueStableContextV1,
    GlueUnsafeContextV1,
)


def stable_provider(context: GlueStableContextV1):
    return _StableDuplicatePartition(context)


def application_provider(context: GlueApplicationContextV1):
    return _ApplicationDuplicatePartition(context)


def unsafe_provider(context: GlueUnsafeContextV1):
    return _UnsafeDuplicatePartition(context)


class _StableDuplicatePartition:
    def __init__(self, context: GlueStableContextV1) -> None:
        self._context = context

    async def invoke(self, call: OperationCall, next_handler: OperationNext):
        try:
            return await next_handler(call)
        except AwsServiceError as error:
            if error.code != "AlreadyExistsException":
                raise
            catalog_id, database, table, values = _partition_key(
                call, self._context.default_catalog_id
            )
            existing = await self._context.catalog.get_partition(
                catalog_id, database, table, values
            )
            raise AwsServiceError(
                error.code,
                f"stable example observed existing partition {list(existing.values)!r}",
                http_status=error.http_status,
            ) from error


class _ApplicationDuplicatePartition:
    def __init__(self, context: GlueApplicationContextV1) -> None:
        self._context = context

    async def invoke(self, call: OperationCall, next_handler: OperationNext):
        try:
            return await next_handler(call)
        except AwsServiceError as error:
            if error.code != "AlreadyExistsException":
                raise
            catalog_id, database, table, values = _partition_key(
                call, self._context.default_catalog_id
            )
            await self._context.application.get_partition(catalog_id, database, table, values)
            raise


class _UnsafeDuplicatePartition:
    def __init__(self, context: GlueUnsafeContextV1) -> None:
        self._context = context

    async def invoke(self, call: OperationCall, next_handler: OperationNext):
        try:
            return await next_handler(call)
        except AwsServiceError as error:
            if error.code != "AlreadyExistsException":
                raise
            catalog_id, database, table, values = _partition_key(
                call, self._context.settings.policy.default_catalog_id
            )
            await self._context.repository.get_partition(catalog_id, database, table, values)
            raise


def _partition_key(
    call: OperationCall,
    default_catalog_id: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    payload: dict[str, Any] = dict(call.payload)
    definition = payload["PartitionInput"]
    if not isinstance(definition, dict):
        raise TypeError("PartitionInput must be a mapping")
    return (
        str(payload.get("CatalogId", default_catalog_id)),
        str(payload["DatabaseName"]),
        str(payload["TableName"]),
        tuple(map(str, definition["Values"])),
    )
