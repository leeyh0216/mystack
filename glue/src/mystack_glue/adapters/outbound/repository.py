"""Concurrency-safe Data Catalog repository with isolated aggregate copies.

References:
- https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_TableVersion.html
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from pathlib import Path
from typing import Any

from mystack_aws_protocol.observability import log_event

from mystack_glue.domain import (
    AlreadyExistsError,
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    EntityNotFoundError,
    VersionMismatchError,
)

_LOGGER = logging.getLogger(__name__)
_DatabaseKey = tuple[str, str]
_TableKey = tuple[str, str, str]
_PartitionKey = tuple[str, str, str, tuple[str, ...]]


class InMemoryCatalogRepository:
    def __init__(self) -> None:
        self._databases: dict[_DatabaseKey, CatalogDatabase] = {}
        self._tables: dict[_TableKey, CatalogTable] = {}
        self._partitions: dict[_PartitionKey, CatalogPartition] = {}
        self._lock = asyncio.Lock()

    async def create_database(self, database: CatalogDatabase) -> None:
        key = (database.catalog_id, database.name)
        async with self._lock:
            if key in self._databases:
                raise AlreadyExistsError(f"Database {database.name!r} already exists")
            self._databases[key] = copy.deepcopy(database)
        self._log("glue.repository.database.created", "database", key)

    async def get_database(self, catalog_id: str, name: str) -> CatalogDatabase:
        async with self._lock:
            value = self._databases.get((catalog_id, name))
            if value is None:
                raise EntityNotFoundError(f"Database {name!r} does not exist")
            return copy.deepcopy(value)

    async def list_databases(self, catalog_id: str) -> list[CatalogDatabase]:
        async with self._lock:
            return copy.deepcopy(
                [value for key, value in self._databases.items() if key[0] == catalog_id]
            )

    async def update_database(self, old_name: str, database: CatalogDatabase) -> None:
        old_key = (database.catalog_id, old_name)
        new_key = (database.catalog_id, database.name)
        async with self._lock:
            if old_key not in self._databases:
                raise EntityNotFoundError(f"Database {old_name!r} does not exist")
            if new_key != old_key and new_key in self._databases:
                raise AlreadyExistsError(f"Database {database.name!r} already exists")
            self._databases.pop(old_key)
            self._databases[new_key] = copy.deepcopy(database)
            if old_key != new_key:
                self._rename_database_children(database.catalog_id, old_name, database.name)
        self._log("glue.repository.database.updated", "database", new_key)

    async def delete_database(self, catalog_id: str, name: str) -> None:
        key = (catalog_id, name)
        async with self._lock:
            if self._databases.pop(key, None) is None:
                raise EntityNotFoundError(f"Database {name!r} does not exist")
            table_keys = [value for value in self._tables if value[:2] == key]
            for table_key in table_keys:
                self._tables.pop(table_key)
            partition_keys = [value for value in self._partitions if value[:2] == key]
            for partition_key in partition_keys:
                self._partitions.pop(partition_key)
        self._log("glue.repository.database.deleted", "database", key)

    async def create_table(self, table: CatalogTable) -> None:
        key = (table.catalog_id, table.database_name, table.name)
        async with self._lock:
            if key in self._tables:
                raise AlreadyExistsError(f"Table {table.database_name}.{table.name} already exists")
            self._tables[key] = copy.deepcopy(table)
        self._log("glue.repository.table.created", "table", key)

    async def get_table(self, catalog_id: str, database: str, name: str) -> CatalogTable:
        key = (catalog_id, database, name)
        async with self._lock:
            value = self._tables.get(key)
            if value is None:
                raise EntityNotFoundError(f"Table {database}.{name} does not exist")
            return copy.deepcopy(value)

    async def list_tables(self, catalog_id: str, database: str) -> list[CatalogTable]:
        async with self._lock:
            return copy.deepcopy(
                [value for key, value in self._tables.items() if key[:2] == (catalog_id, database)]
            )

    async def update_table(
        self,
        old_name: str,
        table: CatalogTable,
        *,
        expected_version_id: str | None,
        skip_archive: bool,
    ) -> None:
        old_key = (table.catalog_id, table.database_name, old_name)
        new_key = (table.catalog_id, table.database_name, table.name)
        async with self._lock:
            current = self._tables.get(old_key)
            if current is None:
                raise EntityNotFoundError(f"Table {table.database_name}.{old_name} does not exist")
            if expected_version_id is not None and current.version_id != expected_version_id:
                raise VersionMismatchError(
                    f"Expected table version {expected_version_id}, "
                    f"current version is {current.version_id}"
                )
            if new_key != old_key and new_key in self._tables:
                raise AlreadyExistsError(f"Table {table.database_name}.{table.name} already exists")
            table.archived_versions = copy.deepcopy(current.archived_versions)
            if not skip_archive:
                table.archived_versions.append(_version(current))
            self._tables.pop(old_key)
            self._tables[new_key] = copy.deepcopy(table)
            if new_key != old_key:
                self._rename_table_partitions(
                    table.catalog_id, table.database_name, old_name, table.name
                )
        self._log("glue.repository.table.updated", "table", new_key)

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None:
        key = (catalog_id, database, name)
        async with self._lock:
            if self._tables.pop(key, None) is None:
                raise EntityNotFoundError(f"Table {database}.{name} does not exist")
            partition_keys = [value for value in self._partitions if value[:3] == key]
            for partition_key in partition_keys:
                self._partitions.pop(partition_key)
        self._log("glue.repository.table.deleted", "table", key)

    async def get_table_version(
        self,
        catalog_id: str,
        database: str,
        table: str,
        version_id: str | None,
    ) -> CatalogTableVersion:
        current = await self.get_table(catalog_id, database, table)
        versions = [*current.archived_versions, _version(current)]
        if version_id is None:
            return versions[-1]
        for value in versions:
            if value.version_id == version_id:
                return value
        raise EntityNotFoundError(f"Table version {database}.{table}@{version_id} does not exist")

    async def list_table_versions(
        self,
        catalog_id: str,
        database: str,
        table: str,
    ) -> list[CatalogTableVersion]:
        current = await self.get_table(catalog_id, database, table)
        return [*current.archived_versions, _version(current)]

    async def create_partition(self, partition: CatalogPartition) -> None:
        key = _partition_key(partition)
        async with self._lock:
            if key in self._partitions:
                raise AlreadyExistsError(f"Partition {list(partition.values)!r} already exists")
            self._partitions[key] = copy.deepcopy(partition)
        self._log("glue.repository.partition.created", "partition", key)

    async def get_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> CatalogPartition:
        key = (catalog_id, database, table, values)
        async with self._lock:
            value = self._partitions.get(key)
            if value is None:
                raise EntityNotFoundError(f"Partition {list(values)!r} does not exist")
            return copy.deepcopy(value)

    async def list_partitions(
        self,
        catalog_id: str,
        database: str,
        table: str,
    ) -> list[CatalogPartition]:
        prefix = (catalog_id, database, table)
        async with self._lock:
            return copy.deepcopy(
                [value for key, value in self._partitions.items() if key[:3] == prefix]
            )

    async def update_partition(
        self,
        old_values: tuple[str, ...],
        partition: CatalogPartition,
    ) -> None:
        old_key = (
            partition.catalog_id,
            partition.database_name,
            partition.table_name,
            old_values,
        )
        new_key = _partition_key(partition)
        async with self._lock:
            if old_key not in self._partitions:
                raise EntityNotFoundError(f"Partition {list(old_values)!r} does not exist")
            if old_key != new_key and new_key in self._partitions:
                raise AlreadyExistsError(f"Partition {list(partition.values)!r} already exists")
            self._partitions.pop(old_key)
            self._partitions[new_key] = copy.deepcopy(partition)
        self._log("glue.repository.partition.updated", "partition", new_key)

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None:
        key = (catalog_id, database, table, values)
        async with self._lock:
            if self._partitions.pop(key, None) is None:
                raise EntityNotFoundError(f"Partition {list(values)!r} does not exist")
        self._log("glue.repository.partition.deleted", "partition", key)

    def _rename_database_children(self, catalog_id: str, old: str, new: str) -> None:
        for key in [value for value in self._tables if value[:2] == (catalog_id, old)]:
            table = self._tables.pop(key)
            table.database_name = new
            self._tables[(catalog_id, new, table.name)] = table
        for key in [value for value in self._partitions if value[:2] == (catalog_id, old)]:
            partition = self._partitions.pop(key)
            partition.database_name = new
            self._partitions[_partition_key(partition)] = partition

    def _rename_table_partitions(
        self,
        catalog_id: str,
        database: str,
        old: str,
        new: str,
    ) -> None:
        prefix = (catalog_id, database, old)
        for key in [value for value in self._partitions if value[:3] == prefix]:
            partition = self._partitions.pop(key)
            partition.table_name = new
            self._partitions[_partition_key(partition)] = partition

    @staticmethod
    def _log(event: str, resource_type: str, key: tuple) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            event,
            resource_type=resource_type,
            resource_key_fingerprint=hash(key),
            side_effect=True,
        )


def _partition_key(partition: CatalogPartition) -> _PartitionKey:
    return (
        partition.catalog_id,
        partition.database_name,
        partition.table_name,
        partition.values,
    )


def _version(table: CatalogTable) -> CatalogTableVersion:
    return CatalogTableVersion(
        version_id=table.version_id,
        definition=copy.deepcopy(table.definition),
        create_time=table.create_time,
        update_time=table.update_time,
    )


class JsonCatalogRepository(InMemoryCatalogRepository):
    """Durable JSON adapter using atomic same-directory replacement.

    Atomic replacement reference:
    https://docs.python.org/3/library/os.html#os.replace
    """

    def __init__(self, state_file: Path) -> None:
        super().__init__()
        self._state_file = state_file
        self._persist_lock = asyncio.Lock()
        self._load()

    async def create_database(self, database: CatalogDatabase) -> None:
        await super().create_database(database)
        await self._persist()

    async def update_database(self, old_name: str, database: CatalogDatabase) -> None:
        await super().update_database(old_name, database)
        await self._persist()

    async def delete_database(self, catalog_id: str, name: str) -> None:
        await super().delete_database(catalog_id, name)
        await self._persist()

    async def create_table(self, table: CatalogTable) -> None:
        await super().create_table(table)
        await self._persist()

    async def update_table(
        self,
        old_name: str,
        table: CatalogTable,
        *,
        expected_version_id: str | None,
        skip_archive: bool,
    ) -> None:
        await super().update_table(
            old_name,
            table,
            expected_version_id=expected_version_id,
            skip_archive=skip_archive,
        )
        await self._persist()

    async def delete_table(self, catalog_id: str, database: str, name: str) -> None:
        await super().delete_table(catalog_id, database, name)
        await self._persist()

    async def create_partition(self, partition: CatalogPartition) -> None:
        await super().create_partition(partition)
        await self._persist()

    async def update_partition(
        self,
        old_values: tuple[str, ...],
        partition: CatalogPartition,
    ) -> None:
        await super().update_partition(old_values, partition)
        await self._persist()

    async def delete_partition(
        self,
        catalog_id: str,
        database: str,
        table: str,
        values: tuple[str, ...],
    ) -> None:
        await super().delete_partition(catalog_id, database, table, values)
        await self._persist()

    async def _persist(self) -> None:
        async with self._persist_lock:
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.persist.before",
                state_file=str(self._state_file),
                side_effect=True,
            )
            async with self._lock:
                document = {
                    "schema_version": 1,
                    "databases": [_database_document(value) for value in self._databases.values()],
                    "tables": [_table_document(value) for value in self._tables.values()],
                    "partitions": [
                        _partition_document(value) for value in self._partitions.values()
                    ],
                }
            serialized = json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            await asyncio.to_thread(self._write_atomic, serialized)
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.persist.after",
                state_file=str(self._state_file),
                size_bytes=len(serialized.encode()),
                database_count=len(document["databases"]),
                table_count=len(document["tables"]),
                partition_count=len(document["partitions"]),
                side_effect=True,
            )

    def _load(self) -> None:
        if not self._state_file.exists():
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.load.empty",
                state_file=str(self._state_file),
            )
            return
        try:
            document = json.loads(self._state_file.read_text(encoding="utf-8"))
            if document.get("schema_version") != 1:
                raise ValueError("Unsupported catalog state schema_version")
            for raw in document.get("databases", ()):
                value = _database_from_document(raw)
                self._databases[(value.catalog_id, value.name)] = value
            for raw in document.get("tables", ()):
                value = _table_from_document(raw)
                self._tables[(value.catalog_id, value.database_name, value.name)] = value
            for raw in document.get("partitions", ()):
                value = _partition_from_document(raw)
                self._partitions[_partition_key(value)] = value
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.repository.load.failed",
                state_file=str(self._state_file),
                fix_hint=(
                    "Restore a catalog-state.json file with schema_version 1 or move the "
                    "invalid file aside before restarting."
                ),
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.repository.load.completed",
            state_file=str(self._state_file),
            database_count=len(self._databases),
            table_count=len(self._tables),
            partition_count=len(self._partitions),
        )

    def _write_atomic(self, serialized: str) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_file.with_suffix(f"{self._state_file.suffix}.tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(self._state_file)


def _database_document(value: CatalogDatabase) -> dict[str, Any]:
    return {
        "catalog_id": value.catalog_id,
        "name": value.name,
        "definition": value.definition,
        "create_time": value.create_time,
    }


def _database_from_document(value: dict[str, Any]) -> CatalogDatabase:
    return CatalogDatabase(
        catalog_id=str(value["catalog_id"]),
        name=str(value["name"]),
        definition=dict(value["definition"]),
        create_time=float(value["create_time"]),
    )


def _table_document(value: CatalogTable) -> dict[str, Any]:
    return {
        "catalog_id": value.catalog_id,
        "database_name": value.database_name,
        "name": value.name,
        "definition": value.definition,
        "create_time": value.create_time,
        "update_time": value.update_time,
        "version_id": value.version_id,
        "archived_versions": [
            {
                "version_id": version.version_id,
                "definition": version.definition,
                "create_time": version.create_time,
                "update_time": version.update_time,
            }
            for version in value.archived_versions
        ],
    }


def _table_from_document(value: dict[str, Any]) -> CatalogTable:
    return CatalogTable(
        catalog_id=str(value["catalog_id"]),
        database_name=str(value["database_name"]),
        name=str(value["name"]),
        definition=dict(value["definition"]),
        create_time=float(value["create_time"]),
        update_time=float(value["update_time"]),
        version_id=str(value["version_id"]),
        archived_versions=[
            CatalogTableVersion(
                version_id=str(version["version_id"]),
                definition=dict(version["definition"]),
                create_time=float(version["create_time"]),
                update_time=float(version["update_time"]),
            )
            for version in value.get("archived_versions", ())
        ],
    )


def _partition_document(value: CatalogPartition) -> dict[str, Any]:
    return {
        "catalog_id": value.catalog_id,
        "database_name": value.database_name,
        "table_name": value.table_name,
        "values": list(value.values),
        "definition": value.definition,
        "creation_time": value.creation_time,
        "update_time": value.update_time,
    }


def _partition_from_document(value: dict[str, Any]) -> CatalogPartition:
    return CatalogPartition(
        catalog_id=str(value["catalog_id"]),
        database_name=str(value["database_name"]),
        table_name=str(value["table_name"]),
        values=tuple(map(str, value["values"])),
        definition=dict(value["definition"]),
        creation_time=float(value["creation_time"]),
        update_time=float(value["update_time"]),
    )
