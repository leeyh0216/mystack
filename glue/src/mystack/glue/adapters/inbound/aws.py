"""Translate Glue AWS JSON 1.1 Data Catalog operations to application use cases.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
- https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from mystack.aws_protocol import (
    AwsRequestContext,
    AwsServiceError,
    OperationDispatcher,
)
from mystack.glue.application.use_cases import GlueCatalogUseCases
from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)
from mystack.glue.domain.errors import GlueDomainError

Handler = Callable[[Mapping[str, Any], AwsRequestContext], Awaitable[Mapping[str, Any]]]


class GlueAwsAdapter:
    def __init__(self, application: GlueCatalogUseCases, default_catalog_id: str) -> None:
        self._application = application
        self._default_catalog_id = default_catalog_id

    def dispatcher(self) -> OperationDispatcher:
        handlers: dict[str, Handler] = {
            "BatchCreatePartition": self.batch_create_partition,
            "BatchDeletePartition": self.batch_delete_partition,
            "BatchGetPartition": self.batch_get_partition,
            "BatchUpdatePartition": self.batch_update_partition,
            "CreateDatabase": self.create_database,
            "CreatePartition": self.create_partition,
            "CreateTable": self.create_table,
            "DeleteDatabase": self.delete_database,
            "DeletePartition": self.delete_partition,
            "DeleteTable": self.delete_table,
            "GetCatalogImportStatus": self.get_catalog_import_status,
            "GetDatabase": self.get_database,
            "GetDatabases": self.get_databases,
            "GetPartition": self.get_partition,
            "GetPartitions": self.get_partitions,
            "GetTable": self.get_table,
            "GetTables": self.get_tables,
            "GetTableVersion": self.get_table_version,
            "GetTableVersions": self.get_table_versions,
            "UpdateDatabase": self.update_database,
            "UpdatePartition": self.update_partition,
            "UpdateTable": self.update_table,
        }
        return OperationDispatcher(
            {name: self._translate_errors(handler) for name, handler in handlers.items()}
        )

    async def create_database(self, payload, context):
        del context
        await self._application.create_database(
            self._catalog(payload),
            dict(_mapping(payload["DatabaseInput"], "DatabaseInput")),
        )
        return {}

    async def get_database(self, payload, context):
        del context
        value = await self._application.get_database(self._catalog(payload), str(payload["Name"]))
        return {"Database": _database(value)}

    async def get_databases(self, payload, context):
        del context
        values, token = await self._application.get_databases(
            self._catalog(payload),
            next_token=_optional_string(payload.get("NextToken")),
            max_results=_optional_int(payload.get("MaxResults")),
        )
        return _with_token({"DatabaseList": [_database(value) for value in values]}, token)

    async def update_database(self, payload, context):
        del context
        await self._application.update_database(
            self._catalog(payload),
            str(payload["Name"]),
            dict(_mapping(payload["DatabaseInput"], "DatabaseInput")),
        )
        return {}

    async def delete_database(self, payload, context):
        del context
        await self._application.delete_database(self._catalog(payload), str(payload["Name"]))
        return {}

    async def create_table(self, payload, context):
        del context
        definition = payload.get("TableInput")
        if definition is None:
            raise InvalidInputError(
                "Mystack currently requires TableInput; OpenTableFormatInput is not implemented"
            )
        await self._application.create_table(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            dict(_mapping(definition, "TableInput")),
        )
        return {}

    async def get_table(self, payload, context):
        del context
        value = await self._application.get_table(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["Name"]),
        )
        return {"Table": _table(value)}

    async def get_tables(self, payload, context):
        del context
        values, token = await self._application.get_tables(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            expression=_optional_string(payload.get("Expression")),
            next_token=_optional_string(payload.get("NextToken")),
            max_results=_optional_int(payload.get("MaxResults")),
        )
        attributes = set(map(str, payload.get("AttributesToGet", ())))
        tables = [_table(value) for value in values]
        if attributes:
            tables = [
                {key: value for key, value in table.items() if key in _attribute_keys(attributes)}
                for table in tables
            ]
        return _with_token({"TableList": tables}, token)

    async def update_table(self, payload, context):
        del context
        definition = payload.get("TableInput")
        if definition is None:
            raise InvalidInputError(
                "Mystack currently requires TableInput; "
                "UpdateOpenTableFormatInput is not implemented"
            )
        old_name = str(payload.get("Name") or _mapping(definition, "TableInput")["Name"])
        await self._application.update_table(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            old_name,
            dict(_mapping(definition, "TableInput")),
            version_id=_optional_string(payload.get("VersionId")),
            skip_archive=bool(payload.get("SkipArchive", False)),
        )
        return {}

    async def delete_table(self, payload, context):
        del context
        await self._application.delete_table(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["Name"]),
        )
        return {}

    async def get_table_version(self, payload, context):
        del context
        catalog_id = self._catalog(payload)
        database = str(payload["DatabaseName"])
        value = await self._application.get_table_version(
            catalog_id,
            database,
            str(payload["TableName"]),
            _optional_string(payload.get("VersionId")),
        )
        return {"TableVersion": _table_version(value, catalog_id, database)}

    async def get_table_versions(self, payload, context):
        del context
        catalog_id = self._catalog(payload)
        database = str(payload["DatabaseName"])
        values, token = await self._application.get_table_versions(
            catalog_id,
            database,
            str(payload["TableName"]),
            next_token=_optional_string(payload.get("NextToken")),
            max_results=_optional_int(payload.get("MaxResults")),
        )
        result = {
            "TableVersions": [_table_version(value, catalog_id, database) for value in values]
        }
        return _with_token(result, token)

    async def create_partition(self, payload, context):
        del context
        await self._application.create_partition(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            dict(_mapping(payload["PartitionInput"], "PartitionInput")),
        )
        return {}

    async def batch_create_partition(self, payload, context):
        del context
        definitions = [
            dict(_mapping(definition, "PartitionInput"))
            for definition in payload["PartitionInputList"]
        ]
        failures = await self._application.batch_create_partitions(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            definitions,
        )
        return {
            "Errors": [
                _partition_error(list(failure.values), failure.error) for failure in failures
            ]
        }

    async def get_partition(self, payload, context):
        del context
        value = await self._application.get_partition(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValues"])),
        )
        return {"Partition": _partition(value)}

    async def get_partitions(self, payload, context):
        del context
        raw_segment = payload.get("Segment")
        segment = None
        if raw_segment is not None:
            segment_value = _mapping(raw_segment, "Segment")
            segment = (int(segment_value["SegmentNumber"]), int(segment_value["TotalSegments"]))
        values, token = await self._application.get_partitions(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            expression=_optional_string(payload.get("Expression")),
            segment=segment,
            next_token=_optional_string(payload.get("NextToken")),
            max_results=_optional_int(payload.get("MaxResults")),
        )
        partitions = [_partition(value) for value in values]
        if payload.get("ExcludeColumnSchema"):
            partitions = [_without_columns(value) for value in partitions]
        return _with_token({"Partitions": partitions}, token)

    async def batch_get_partition(self, payload, context):
        del context
        value_groups = [
            tuple(map(str, _mapping(key, "PartitionsToGet[]")["Values"]))
            for key in payload["PartitionsToGet"]
        ]
        partitions = await self._application.batch_get_partitions(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            value_groups,
        )
        return {
            "Partitions": [_partition(value) for value in partitions],
            "UnprocessedKeys": [],
        }

    async def update_partition(self, payload, context):
        del context
        await self._application.update_partition(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValueList"])),
            dict(_mapping(payload["PartitionInput"], "PartitionInput")),
        )
        return {}

    async def batch_update_partition(self, payload, context):
        del context
        entries = []
        for entry in payload["Entries"]:
            item = _mapping(entry, "Entries[]")
            entries.append(
                (
                    tuple(map(str, item["PartitionValueList"])),
                    dict(_mapping(item["PartitionInput"], "PartitionInput")),
                )
            )
        failures = await self._application.batch_update_partitions(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            entries,
        )
        return {
            "Errors": [
                {
                    "PartitionValueList": list(failure.values),
                    "ErrorDetail": _error_detail(failure.error),
                }
                for failure in failures
            ]
        }

    async def delete_partition(self, payload, context):
        del context
        await self._application.delete_partition(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            tuple(map(str, payload["PartitionValues"])),
        )
        return {}

    async def batch_delete_partition(self, payload, context):
        del context
        value_groups = [
            tuple(map(str, _mapping(key, "PartitionsToDelete[]")["Values"]))
            for key in payload["PartitionsToDelete"]
        ]
        failures = await self._application.batch_delete_partitions(
            self._catalog(payload),
            str(payload["DatabaseName"]),
            str(payload["TableName"]),
            value_groups,
        )
        return {
            "Errors": [
                _partition_error(list(failure.values), failure.error) for failure in failures
            ]
        }

    async def get_catalog_import_status(self, payload, context):
        del context
        return {
            "ImportStatus": {
                "ImportCompleted": True,
                "ImportTime": 0.0,
                "ImportedBy": "mystack",
            }
        }

    def _catalog(self, payload: Mapping[str, Any]) -> str:
        return str(payload.get("CatalogId", self._default_catalog_id))

    def _translate_errors(self, handler: Handler) -> Handler:
        async def translated(payload, context):
            try:
                return await handler(payload, context)
            except GlueDomainError as error:
                code = _error_code(error)
                raise AwsServiceError(
                    code,
                    str(error),
                    http_status=400,
                    fix_hint=(
                        "Compare the Glue inbound mapper and domain invariant with the pinned "
                        "service model and AWS Glue API error list."
                    ),
                ) from error
            except (KeyError, TypeError, ValueError) as error:
                raise AwsServiceError(
                    "InvalidInputException",
                    str(error),
                    http_status=400,
                    fix_hint=(
                        "Inspect mystack.glue/adapters/inbound/aws.py for shape mapping drift."
                    ),
                ) from error

        return translated


def _database(value: CatalogDatabase) -> dict[str, Any]:
    result = copy.deepcopy(value.definition)
    result.update({"CatalogId": value.catalog_id, "CreateTime": value.create_time})
    return result


def _table(value: CatalogTable) -> dict[str, Any]:
    return _table_document(
        value.definition,
        value.catalog_id,
        value.database_name,
        value.create_time,
        value.update_time,
        value.version_id,
    )


def _table_version(
    value: CatalogTableVersion,
    catalog_id: str,
    database: str,
) -> dict[str, Any]:
    return {
        "VersionId": value.version_id,
        "Table": _table_document(
            value.definition,
            catalog_id,
            database,
            value.create_time,
            value.update_time,
            value.version_id,
        ),
    }


def _table_document(definition, catalog_id, database, create_time, update_time, version_id):
    result = copy.deepcopy(definition)
    # The Glue 5 Spark client unboxes this modeled Boolean. AWS responses provide
    # false for ordinary tables even though the service model does not mark it required.
    # API field: https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
    result.setdefault("IsRegisteredWithLakeFormation", False)
    result.update(
        {
            "CatalogId": catalog_id,
            "DatabaseName": database,
            "CreateTime": create_time,
            "UpdateTime": update_time,
            "VersionId": version_id,
        }
    )
    return result


def _partition(value: CatalogPartition) -> dict[str, Any]:
    result = copy.deepcopy(value.definition)
    result.update(
        {
            "CatalogId": value.catalog_id,
            "DatabaseName": value.database_name,
            "TableName": value.table_name,
            "CreationTime": value.creation_time,
        }
    )
    return result


def _without_columns(partition: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(partition)
    descriptor = result.get("StorageDescriptor")
    if isinstance(descriptor, dict):
        descriptor.pop("Columns", None)
    return result


def _attribute_keys(attributes: set[str]) -> set[str]:
    keys = {"Name"}
    if "TABLE_TYPE" in attributes:
        keys.add("TableType")
    return keys


def _partition_error(values: list[str], error: GlueDomainError) -> dict[str, Any]:
    return {"PartitionValues": values, "ErrorDetail": _error_detail(error)}


def _error_detail(error: GlueDomainError) -> dict[str, str]:
    return {"ErrorCode": _error_code(error), "ErrorMessage": str(error)}


def _error_code(error: GlueDomainError) -> str:
    if isinstance(error, AlreadyExistsError):
        return "AlreadyExistsException"
    if isinstance(error, EntityNotFoundError):
        return "EntityNotFoundException"
    if isinstance(error, VersionMismatchError):
        return "VersionMismatchException"
    return "InvalidInputException"


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _with_token(result: dict[str, Any], token: str | None) -> dict[str, Any]:
    if token is not None:
        result["NextToken"] = token
    return result
