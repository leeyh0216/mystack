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
    InvalidInputError,
    TableOptimizer,
    TableOptimizerRun,
    TableOptimizerType,
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


def table_attribute_keys(attributes: tuple[str, ...], *, supplied: bool) -> set[str]:
    _require_attribute_combination(
        attributes,
        supplied=supplied,
        supported={"NAME", "TABLE_TYPE"},
    )
    keys = {"Name"}
    if "TABLE_TYPE" in attributes:
        keys.add("TableType")
    return keys


def database_attribute_keys(attributes: tuple[str, ...], *, supplied: bool) -> set[str]:
    _require_attribute_combination(
        attributes,
        supplied=supplied,
        supported={"NAME", "TARGET_DATABASE"},
    )
    keys = {"Name"}
    if "TARGET_DATABASE" in attributes:
        keys.add("TargetDatabase")
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


def table_optimizer_document(value: TableOptimizer) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": value.optimizer_type.value,
        "configuration": value.configuration.document,
        "configurationSource": "table",
    }
    if value.last_run is not None:
        result["lastRun"] = table_optimizer_run_document(
            value.last_run,
            value.optimizer_type,
        )
    return result


def table_optimizer_run_document(
    value: TableOptimizerRun,
    optimizer_type: object,
) -> dict[str, Any]:
    parsed_type = TableOptimizerType.parse(optimizer_type)
    result: dict[str, Any] = {
        "eventType": value.event_type.value,
        "startTimestamp": value.start_timestamp,
    }
    if value.end_timestamp is not None:
        result["endTimestamp"] = value.end_timestamp
    if value.error is not None:
        result["error"] = value.error
    if value.metrics is not None:
        result.update(_optimizer_metric_documents(parsed_type, value.metrics))
    configuration = value.configuration or {}
    if parsed_type is TableOptimizerType.COMPACTION:
        iceberg = configuration.get("compactionConfiguration", {}).get("icebergConfiguration", {})
        result["compactionStrategy"] = iceberg.get("strategy", "binpack")
    return result


def _optimizer_metric_documents(
    optimizer_type: TableOptimizerType,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    if optimizer_type is TableOptimizerType.COMPACTION:
        legacy_keys = (
            "NumberOfBytesCompacted",
            "NumberOfFilesCompacted",
            "NumberOfDpus",
            "JobDurationInHour",
        )
        return {
            "metrics": {key: str(metrics[key]) for key in legacy_keys if key in metrics},
            "compactionMetrics": {"IcebergMetrics": copy.deepcopy(metrics)},
        }
    if optimizer_type is TableOptimizerType.RETENTION:
        return {"retentionMetrics": {"IcebergMetrics": copy.deepcopy(metrics)}}
    return {"orphanFileDeletionMetrics": {"IcebergMetrics": copy.deepcopy(metrics)}}


def _require_attribute_combination(
    attributes: tuple[str, ...],
    *,
    supplied: bool,
    supported: set[str],
) -> None:
    if supplied and "NAME" not in attributes:
        raise InvalidInputError("AttributesToGet must include NAME")
    if len(attributes) != len(set(attributes)) or not set(attributes).issubset(supported):
        raise InvalidInputError("AttributesToGet contains an unsupported combination")


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
