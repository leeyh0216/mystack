"""Management read model for Glue Data Catalog resources.

The UI consumes this adapter rather than importing Domain types. Official resource model:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.use_cases import GlueManagementQueries
from mystack.glue.domain import CatalogDatabase, CatalogPartition, CatalogTable

_LOGGER = logging.getLogger(__name__)
_Item = TypeVar("_Item")


class GlueManagementAdapter:
    def __init__(
        self,
        application: GlueManagementQueries,
        *,
        catalog_id: str,
        api_page_size: int,
        implemented_operations: frozenset[str],
        model_operation_count: int,
        runtime_profile: str,
        config_fingerprint: str,
    ) -> None:
        self._application = application
        self._catalog_id = catalog_id
        self._api_page_size = api_page_size
        self._implemented_operations = implemented_operations
        self._model_operation_count = model_operation_count
        self._runtime_profile = runtime_profile
        self._config_fingerprint = config_fingerprint

    async def resources(self) -> dict[str, Any]:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.management.resources.before",
            catalog_id=self._catalog_id,
        )
        databases = await self._all(
            lambda token: self._application.get_databases(
                self._catalog_id,
                next_token=token,
                max_results=self._api_page_size,
            )
        )
        rendered: list[dict[str, Any]] = []
        table_count = 0
        partition_count = 0
        for database in databases:
            tables = await self._all(
                lambda token, name=database.name: self._application.get_tables(
                    self._catalog_id,
                    name,
                    expression=None,
                    next_token=token,
                    max_results=self._api_page_size,
                )
            )
            rendered_tables: list[dict[str, Any]] = []
            for table in tables:
                partitions = await self._all(
                    lambda token, database_name=database.name, table_name=table.name: (
                        self._application.get_partitions(
                            self._catalog_id,
                            database_name,
                            table_name,
                            expression=None,
                            segment=None,
                            next_token=token,
                            max_results=self._api_page_size,
                        )
                    )
                )
                rendered_tables.append(_table(table, partitions))
                partition_count += len(partitions)
            table_count += len(tables)
            rendered.append(_database(database, rendered_tables))
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.management.resources.after",
            catalog_id=self._catalog_id,
            database_count=len(rendered),
            table_count=table_count,
            partition_count=partition_count,
        )
        return {
            "schema_version": 1,
            "service": "glue",
            "emulator": {
                "mode": "Glue Data Catalog",
                "runtime_profile": self._runtime_profile,
                "config_fingerprint": self._config_fingerprint,
                "notice": "Glue Jobs, JobRuns, and Crawlers are explicitly out of scope.",
            },
            "compatibility": {
                "classification": "PARTIAL",
                "implemented_operation_count": len(self._implemented_operations),
                "model_operation_count": self._model_operation_count,
                "implemented_operations": sorted(self._implemented_operations),
            },
            "counts": {
                "databases": len(rendered),
                "tables": table_count,
                "partitions": partition_count,
            },
            "resources": {"databases": rendered},
        }

    async def _all(
        self,
        page: Callable[[str | None], Awaitable[tuple[list[_Item], str | None]]],
    ) -> list[_Item]:
        values: list[_Item] = []
        token: str | None = None
        while True:
            current, token = await page(token)
            values.extend(current)
            if token is None:
                return values


def _database(value: CatalogDatabase, tables: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": value.name,
        "name": value.name,
        "created_at": _timestamp(value.create_time),
        "description": value.definition.get("Description"),
        "location_uri": value.definition.get("LocationUri"),
        "parameters": value.definition.get("Parameters", {}),
        "definition": value.definition,
        "tables": tables,
    }


def _table(value: CatalogTable, partitions: list[CatalogPartition]) -> dict[str, Any]:
    storage = value.definition.get("StorageDescriptor", {})
    return {
        "id": f"{value.database_name}/{value.name}",
        "name": value.name,
        "database_name": value.database_name,
        "table_type": value.definition.get("TableType"),
        "location": storage.get("Location"),
        "columns": storage.get("Columns", []),
        "partition_keys": value.definition.get("PartitionKeys", []),
        "parameters": value.definition.get("Parameters", {}),
        "version_id": value.version_id,
        "archived_version_count": len(value.archived_versions),
        "created_at": _timestamp(value.create_time),
        "updated_at": _timestamp(value.update_time),
        "definition": value.definition,
        "partitions": [_partition(partition) for partition in partitions],
    }


def _partition(value: CatalogPartition) -> dict[str, Any]:
    return {
        "id": "/".join(value.values),
        "values": list(value.values),
        "created_at": _timestamp(value.creation_time),
        "updated_at": _timestamp(value.update_time),
        "definition": value.definition,
    }


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat()
