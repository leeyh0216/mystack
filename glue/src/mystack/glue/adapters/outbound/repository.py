"""Candidate-state transactions and composed Glue Catalog persistence.

References:
- https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_TableVersion.html
- https://docs.python.org/3/library/os.html#os.replace
- https://docs.python.org/3/library/os.html#os.fsync
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any, Protocol

from mystack.aws_protocol.observability import log_event
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogState,
    CatalogTable,
    CatalogTableVersion,
)

_LOGGER = logging.getLogger(__name__)
_CURRENT_SCHEMA_VERSION = 2


class CatalogStateStore(Protocol):
    """Durability capability composed behind the repository transaction."""

    def load(self) -> CatalogState: ...

    async def save(self, candidate: CatalogState) -> None: ...


class VolatileCatalogStateStore:
    def __init__(self, initial: CatalogState | None = None) -> None:
        self._committed = copy.deepcopy(initial or CatalogState())

    def load(self) -> CatalogState:
        return copy.deepcopy(self._committed)

    async def save(self, candidate: CatalogState) -> None:
        self._committed = copy.deepcopy(candidate)


class JsonCatalogStateStore:
    """Versioned JSON storage using fsync and same-directory atomic replacement."""

    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file

    def load(self) -> CatalogState:
        if not self._state_file.exists():
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.load.empty",
                state_file=str(self._state_file),
            )
            return CatalogState()
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.repository.load.before",
            state_file=str(self._state_file),
            side_effect=True,
        )
        try:
            document = json.loads(self._state_file.read_text(encoding="utf-8"))
            state, source_schema = _state_from_document(document)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.repository.load.failed",
                state_file=str(self._state_file),
                fix_hint=(
                    "Restore a catalog state file with schema_version 1 or 2; update "
                    "JsonCatalogStateStore migration code for a newly supported schema."
                ),
                side_effect=True,
                exc_info=True,
            )
            raise
        if source_schema != _CURRENT_SCHEMA_VERSION:
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.load.migrated",
                source_schema_version=source_schema,
                target_schema_version=_CURRENT_SCHEMA_VERSION,
                state_file=str(self._state_file),
            )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.repository.load.after",
            state_file=str(self._state_file),
            state_revision=state.revision,
            database_count=len(state.databases),
            table_count=len(state.tables),
            partition_count=len(state.partitions),
            side_effect=True,
        )
        return state

    async def save(self, candidate: CatalogState) -> None:
        document = _state_document(candidate)
        serialized = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.repository.persist.before",
            state_file=str(self._state_file),
            candidate_revision=candidate.revision,
            size_bytes=len(serialized.encode()),
            database_count=len(candidate.databases),
            table_count=len(candidate.tables),
            partition_count=len(candidate.partitions),
            side_effect=True,
        )
        try:
            await asyncio.to_thread(self._write_atomic, serialized)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.repository.persist.failed",
                state_file=str(self._state_file),
                candidate_revision=candidate.revision,
                fix_hint=(
                    "Check state-file permissions, free space, and same-directory atomic "
                    "replacement support; visible state was not published."
                ),
                side_effect=True,
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.repository.persist.after",
            state_file=str(self._state_file),
            committed_revision=candidate.revision,
            size_bytes=len(serialized.encode()),
            side_effect=True,
        )

    def _write_atomic(self, serialized: str) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_file.with_name(f".{self._state_file.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._state_file)
            try:
                directory = os.open(self._state_file.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "glue.repository.persist.directory_fsync_failed",
                    state_file=str(self._state_file),
                    commit_status="replacement-completed",
                    fix_hint=(
                        "The state file was replaced, but directory fsync is unavailable; "
                        "inspect filesystem durability guarantees."
                    ),
                    side_effect=True,
                    exc_info=True,
                )
        finally:
            temporary.unlink(missing_ok=True)


class TransactionalCatalogRepository:
    """Publish a candidate only after its composed state store commits successfully."""

    def __init__(self, store: CatalogStateStore) -> None:
        self._store = store
        self._visible = copy.deepcopy(store.load())
        self._transaction_lock = asyncio.Lock()

    async def snapshot(self) -> CatalogState:
        async with self._transaction_lock:
            snapshot = copy.deepcopy(self._visible)
        log_event(
            _LOGGER,
            logging.DEBUG,
            "glue.repository.snapshot.after",
            state_revision=snapshot.revision,
            database_count=len(snapshot.databases),
            table_count=len(snapshot.tables),
            partition_count=len(snapshot.partitions),
        )
        return snapshot

    @asynccontextmanager
    async def transaction(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
    ) -> AsyncIterator[CatalogState]:
        async with self._transaction_lock:
            base = self._visible
            candidate = copy.deepcopy(base)
            fingerprint = _resource_fingerprint(resource_key)
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.transaction.before",
                operation=operation,
                resource_key_fingerprint=fingerprint,
                visible_revision=base.revision,
                side_effect=True,
            )
            try:
                yield candidate
            except BaseException:
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "glue.repository.transaction.rolled_back",
                    operation=operation,
                    resource_key_fingerprint=fingerprint,
                    visible_revision=base.revision,
                    rollback_reason="mutation-failed",
                    side_effect=True,
                    exc_info=True,
                )
                raise
            candidate.revision = base.revision + 1
            save_task = asyncio.create_task(self._store.save(copy.deepcopy(candidate)))
            cancellation: asyncio.CancelledError | None = None
            try:
                await asyncio.shield(save_task)
            except asyncio.CancelledError as error:
                cancellation = error
                try:
                    await save_task
                except BaseException:
                    self._log_persistence_rollback(
                        operation,
                        fingerprint,
                        base.revision,
                        candidate.revision,
                    )
                    raise
            except Exception:
                self._log_persistence_rollback(
                    operation,
                    fingerprint,
                    base.revision,
                    candidate.revision,
                )
                raise
            self._visible = copy.deepcopy(candidate)
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.repository.transaction.after",
                operation=operation,
                resource_key_fingerprint=fingerprint,
                committed_revision=candidate.revision,
                database_count=len(candidate.databases),
                table_count=len(candidate.tables),
                partition_count=len(candidate.partitions),
                side_effect=True,
            )
            if cancellation is not None:
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "glue.repository.transaction.cancelled_after_commit",
                    operation=operation,
                    resource_key_fingerprint=fingerprint,
                    committed_revision=candidate.revision,
                    side_effect=True,
                )
                raise cancellation

    @staticmethod
    def _log_persistence_rollback(
        operation: str,
        fingerprint: str,
        visible_revision: int,
        candidate_revision: int,
    ) -> None:
        log_event(
            _LOGGER,
            logging.ERROR,
            "glue.repository.transaction.rolled_back",
            operation=operation,
            resource_key_fingerprint=fingerprint,
            visible_revision=visible_revision,
            candidate_revision=candidate_revision,
            rollback_reason="persistence-failed",
            fix_hint=(
                "Repair the composed CatalogStateStore; durable and visible state remain at "
                "visible_revision."
            ),
            side_effect=True,
            exc_info=True,
        )


class InMemoryCatalogRepository:
    """In-memory repository composed from the same transaction coordinator."""

    def __init__(self, initial: CatalogState | None = None) -> None:
        self._delegate = TransactionalCatalogRepository(VolatileCatalogStateStore(initial))

    async def snapshot(self) -> CatalogState:
        return await self._delegate.snapshot()

    def transaction(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
    ) -> AbstractAsyncContextManager[CatalogState]:
        return self._delegate.transaction(operation=operation, resource_key=resource_key)


class JsonCatalogRepository:
    """Durable repository composed with JSON storage rather than inherited behavior."""

    def __init__(self, state_file: Path) -> None:
        self._store = JsonCatalogStateStore(state_file)
        self._delegate = TransactionalCatalogRepository(self._store)

    async def snapshot(self) -> CatalogState:
        return await self._delegate.snapshot()

    def transaction(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
    ) -> AbstractAsyncContextManager[CatalogState]:
        return self._delegate.transaction(operation=operation, resource_key=resource_key)


def _state_document(state: CatalogState) -> dict[str, Any]:
    return {
        "schema_version": _CURRENT_SCHEMA_VERSION,
        "state_revision": state.revision,
        "databases": [_database_document(value) for _, value in sorted(state.databases.items())],
        "tables": [_table_document(value) for _, value in sorted(state.tables.items())],
        "partitions": [_partition_document(value) for _, value in sorted(state.partitions.items())],
    }


def _state_from_document(document: dict[str, Any]) -> tuple[CatalogState, int]:
    schema_version = int(document.get("schema_version", 0))
    if schema_version not in {1, _CURRENT_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported catalog state schema_version {schema_version}")
    revision = int(document.get("state_revision", 0))
    if revision < 0:
        raise ValueError("Catalog state_revision cannot be negative")
    state = CatalogState(revision=revision)
    for raw in document.get("databases", ()):
        value = _database_from_document(raw)
        _insert_unique(state.databases, (value.catalog_id, value.name), value, "database")
    for raw in document.get("tables", ()):
        value = _table_from_document(raw)
        key = (value.catalog_id, value.database_name, value.name)
        _insert_unique(state.tables, key, value, "table")
    for raw in document.get("partitions", ()):
        value = _partition_from_document(raw)
        _insert_unique(state.partitions, _partition_key(value), value, "partition")
    _validate_references(state)
    return state, schema_version


def _insert_unique(target: dict, key: tuple, value: object, kind: str) -> None:
    if key in target:
        raise ValueError(f"Duplicate {kind} key in catalog state")
    target[key] = value


def _validate_references(state: CatalogState) -> None:
    for catalog_id, database, _ in state.tables:
        if (catalog_id, database) not in state.databases:
            raise ValueError("Catalog state table references a missing database")
    for catalog_id, database, table, _ in state.partitions:
        if (catalog_id, database, table) not in state.tables:
            raise ValueError("Catalog state partition references a missing table")


def _resource_fingerprint(resource_key: tuple[object, ...]) -> str:
    return hashlib.sha256(repr(resource_key).encode()).hexdigest()[:16]


def _partition_key(partition: CatalogPartition) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        partition.catalog_id,
        partition.database_name,
        partition.table_name,
        partition.values,
    )


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
