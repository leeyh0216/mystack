"""Glue Data Catalog AWS response shape translation helpers.

Official shapes:
https://docs.aws.amazon.com/glue/latest/webapi/API_Database.html
https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from mystack.glue.adapters.inbound.aws_errors import error_detail
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
)
from mystack.glue.domain.errors import GlueDomainError


def database_document(value: CatalogDatabase) -> dict[str, Any]:
    result = copy.deepcopy(value.definition)
    result.update({"CatalogId": value.catalog_id, "CreateTime": value.create_time})
    return result


def table_document(value: CatalogTable) -> dict[str, Any]:
    return _table_document(
        value.definition,
        value.catalog_id,
        value.database_name,
        value.create_time,
        value.update_time,
        value.version_id,
    )


def table_version_document(
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


def partition_document(value: CatalogPartition) -> dict[str, Any]:
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


def without_columns(partition: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(partition)
    descriptor = result.get("StorageDescriptor")
    if isinstance(descriptor, dict):
        descriptor.pop("Columns", None)
    return result


def attribute_keys(attributes: set[str]) -> set[str]:
    keys = {"Name"}
    if "TABLE_TYPE" in attributes:
        keys.add("TableType")
    return keys


def partition_error(values: list[str], error: GlueDomainError) -> dict[str, Any]:
    return {"PartitionValues": values, "ErrorDetail": error_detail(error)}


def mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    return value


def optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def with_token(result: dict[str, Any], token: str | None) -> dict[str, Any]:
    if token is not None:
        result["NextToken"] = token
    return result


def _table_document(definition, catalog_id, database, create_time, update_time, version_id):
    result = copy.deepcopy(definition)
    # Glue 5 Spark unboxes this modeled Boolean; AWS supplies false for ordinary tables.
    # https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
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
