# ruff: noqa: E501
"""Bounded management read models for the Glue Catalog explorer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.use_cases import GlueManagementQueries
from mystack.glue.domain import CatalogDatabase, CatalogPartition, CatalogTable

_LOGGER = logging.getLogger(__name__)


class GlueManagementAdapter:
    """Expose only UI pages and details; never materialize a catalog tree."""

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
        self._catalog_id, self._api_page_size = catalog_id, api_page_size
        self._implemented_operations, self._model_operation_count = (
            implemented_operations,
            model_operation_count,
        )
        self._runtime_profile, self._config_fingerprint = runtime_profile, config_fingerprint

    async def databases(self, *, cursor: str | None, limit: int | None) -> dict[str, Any]:
        values, next_cursor = await self._application.get_databases(
            self._catalog_id, next_token=cursor, max_results=limit or self._api_page_size
        )
        return self._page(
            "databases",
            [_database(value) for value in values],
            next_cursor,
            await self._application.count_databases(self._catalog_id),
        )

    async def tables(
        self, database_name: str, *, cursor: str | None, limit: int | None
    ) -> dict[str, Any]:
        values, next_cursor = await self._application.get_tables(
            self._catalog_id,
            database_name,
            expression=None,
            next_token=cursor,
            max_results=limit or self._api_page_size,
        )
        return self._page(
            "tables",
            [_table(value) for value in values],
            next_cursor,
            await self._application.count_tables(self._catalog_id, database_name),
        )

    async def table(self, database_name: str, table_name: str) -> dict[str, Any]:
        value = await self._application.get_table(self._catalog_id, database_name, table_name)
        return {
            "schema_version": 2,
            "resource": _table(value),
            "partition_count": await self._application.count_partitions(
                self._catalog_id, database_name, table_name
            ),
            "diagnostics": self._diagnostics("table-detail", "sqlite-point-lookup", 1),
        }

    async def partitions(
        self, database_name: str, table_name: str, *, cursor: str | None, limit: int | None
    ) -> dict[str, Any]:
        values, next_cursor = await self._application.get_partitions(
            self._catalog_id,
            database_name,
            table_name,
            expression=None,
            segment=None,
            next_token=cursor,
            max_results=limit or self._api_page_size,
        )
        return self._page(
            "partitions",
            [_partition(value) for value in values],
            next_cursor,
            await self._application.count_partitions(self._catalog_id, database_name, table_name),
        )

    def _page(
        self, category: str, values: list[dict[str, Any]], next_cursor: str | None, total: int
    ) -> dict[str, Any]:
        document = {
            "schema_version": 2,
            "items": values,
            "next_cursor": next_cursor,
            "total_count": total,
            "diagnostics": self._diagnostics(category, "sqlite-keyset-page", len(values)),
        }
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.management.page.after",
            query_category=category,
            query_strategy="sqlite-keyset-page",
            returned_count=len(values),
            total_count=total,
            has_next=next_cursor is not None,
        )
        return document

    def _diagnostics(self, category: str, strategy: str, returned: int) -> dict[str, Any]:
        return {
            "query_category": category,
            "query_strategy": strategy,
            "returned_count": returned,
            "catalog_id": self._catalog_id,
        }

    def document(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
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
        }


def _database(value: CatalogDatabase) -> dict[str, Any]:
    return {
        "id": value.name,
        "name": value.name,
        "created_at": _timestamp(value.create_time),
        "description": value.definition.get("Description"),
        "location_uri": value.definition.get("LocationUri"),
        "parameters": value.definition.get("Parameters", {}),
    }


def _table(value: CatalogTable) -> dict[str, Any]:
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
