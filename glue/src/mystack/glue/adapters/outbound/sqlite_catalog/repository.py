"""SQLite implementation of the application-owned Glue Catalog ports.

The adapter deliberately returns neutral absence/conditional-write outcomes.  Glue validation,
duplicate precedence, and VersionId error mapping stay in application/domain handlers.

References:
- https://www.sqlite.org/lang_transaction.html
- https://www.sqlite.org/foreignkeys.html
- https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol, TypeVar

from mystack.aws_protocol.observability import log_event
from mystack.glue.adapters.outbound.sqlite_catalog.connection import SqliteCatalogConnectionFactory
from mystack.glue.adapters.outbound.sqlite_catalog.mapping import (
    database_from_row,
    encode_document,
    optimizer_from_rows,
    partition_from_row,
    partition_key_rows,
    partition_values_key,
    table_from_row,
)
from mystack.glue.adapters.outbound.sqlite_catalog.schema import initialize_schema
from mystack.glue.application.catalog_ports import (
    CatalogResourceKey,
    CatalogStore,
    CatalogTransaction,
)
from mystack.glue.application.sqlite_runtime import SQLiteRuntimeSettings
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    TableOptimizer,
)

_LOGGER = logging.getLogger(__name__)
_Result = TypeVar("_Result")


class CatalogTransactionHook(Protocol):
    """Test-only lifecycle seam for deterministic commit failure/cancellation tests."""

    async def before_commit(
        self,
        *,
        operation: str,
        resource_key: CatalogResourceKey,
        mutated: bool,
    ) -> None: ...


class CatalogStorageBusyError(RuntimeError):
    """Configured SQLite writer retries exhausted without choosing a Glue domain error."""


class SqliteCatalogRepository(CatalogStore):
    """One durable normalized SQLite catalog; connections never escape this adapter."""

    def __init__(
        self,
        settings: SQLiteRuntimeSettings,
        *,
        connection_factory: SqliteCatalogConnectionFactory | None = None,
        transaction_hook: CatalogTransactionHook | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._settings = settings
        self._connections = connection_factory or SqliteCatalogConnectionFactory(settings)
        self._transaction_hook = transaction_hook
        self._now = now
        self._initialization_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the schema after the app's SQLite runtime preflight has succeeded."""
        if self._initialized:
            return
        async with self._initialization_lock:
            if self._initialized:
                return
            started = time.monotonic()
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.sqlite_catalog.schema.initialize.before",
                database_file=str(self._settings.database_file),
                journal_mode=self._settings.journal_mode,
                side_effect=True,
            )
            attempts = self._settings.retry_limit + 1
            for attempt in range(1, attempts + 1):
                connection: Any | None = None
                try:
                    connection = self._connections.connect()
                    initialize_schema(connection, now=self._now())
                except Exception as error:
                    if connection is not None:
                        connection.close()
                    if _is_busy(error) and attempt < attempts:
                        delay_seconds = min(0.05 * attempt, 0.25)
                        log_event(
                            _LOGGER,
                            logging.WARNING,
                            "glue.sqlite_catalog.schema.initialize.busy.retry",
                            database_file=str(self._settings.database_file),
                            attempt=attempt,
                            retry_limit=self._settings.retry_limit,
                            delay_seconds=delay_seconds,
                            duration_ms=_duration_ms(started),
                            side_effect=True,
                            fix_hint=(
                                "Inspect concurrent Glue Catalog startup or a long-running writer "
                                "before increasing the SQLite busy timeout or retry limit."
                            ),
                        )
                        await asyncio.sleep(delay_seconds)
                        continue
                    log_event(
                        _LOGGER,
                        logging.ERROR,
                        "glue.sqlite_catalog.schema.initialize.failed",
                        database_file=str(self._settings.database_file),
                        attempt=attempt,
                        duration_ms=_duration_ms(started),
                        side_effect=True,
                        fix_hint=(
                            "Inspect glue.sqlite.database_file volume ownership, the reviewed "
                            "driver, "
                            "and SQLite schema compatibility before retrying."
                        ),
                        exc_info=True,
                    )
                    if _is_busy(error):
                        raise CatalogStorageBusyError(
                            "SQLite catalog schema initialization exceeded the configured "
                            "retry policy"
                        ) from error
                    raise
                else:
                    connection.close()
                    self._initialized = True
                    log_event(
                        _LOGGER,
                        logging.INFO,
                        "glue.sqlite_catalog.schema.initialize.after",
                        database_file=str(self._settings.database_file),
                        attempt=attempt,
                        duration_ms=_duration_ms(started),
                        side_effect=True,
                    )
                    return
            raise AssertionError("SQLite schema initialization retry loop exhausted unexpectedly")

    async def find_database(self, catalog_id: str, database_name: str) -> CatalogDatabase | None:
        def query(connection: Any) -> CatalogDatabase | None:
            record = _database(connection, catalog_id, database_name)
            return None if record is None else record[1]

        return await self._read(
            "find_database",
            query,
        )

    async def list_databases(self, catalog_id: str) -> tuple[CatalogDatabase, ...]:
        return await self._read(
            "list_databases",
            lambda connection: tuple(
                database_from_row(tuple(row))
                for row in connection.execute(
                    "SELECT catalog_id, name, definition_json, create_time "
                    "FROM catalog_databases WHERE catalog_id = ? ORDER BY name",
                    (catalog_id,),
                ).fetchall()
            ),
        )

    async def find_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogTable | None:
        def query(connection: Any) -> CatalogTable | None:
            record = _table(connection, catalog_id, database_name, table_name)
            return None if record is None else record[1]

        return await self._read(
            "find_table",
            query,
        )

    async def list_tables(
        self,
        catalog_id: str,
        database_name: str,
    ) -> tuple[CatalogTable, ...]:
        def query(connection: Any) -> tuple[CatalogTable, ...]:
            rows = connection.execute(
                "SELECT t.table_id, d.catalog_id, d.name, t.name, t.definition_json, "
                "t.create_time, t.update_time, t.version_id "
                "FROM catalog_tables AS t JOIN catalog_databases AS d "
                "ON d.database_id = t.database_id "
                "WHERE d.catalog_id = ? AND d.name = ? ORDER BY t.name",
                (catalog_id, database_name),
            ).fetchall()
            return tuple(_table_from_record(connection, tuple(row))[1] for row in rows)

        return await self._read("list_tables", query)

    async def find_partition(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> CatalogPartition | None:
        def query(connection: Any) -> CatalogPartition | None:
            record = _partition(connection, catalog_id, database_name, table_name, values)
            return None if record is None else record[1]

        return await self._read(
            "find_partition",
            query,
        )

    async def list_partitions(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> tuple[CatalogPartition, ...]:
        def query(connection: Any) -> tuple[CatalogPartition, ...]:
            rows = connection.execute(
                "SELECT p.partition_id, d.catalog_id, d.name, t.name, p.values_json, "
                "p.definition_json, p.creation_time, p.update_time "
                "FROM catalog_partitions AS p "
                "JOIN catalog_tables AS t ON t.table_id = p.table_id "
                "JOIN catalog_databases AS d ON d.database_id = t.database_id "
                "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ?",
                (catalog_id, database_name, table_name),
            ).fetchall()
            return tuple(
                sorted(
                    (partition_from_row(tuple(row[1:])) for row in rows),
                    key=lambda value: value.values,
                )
            )

        return await self._read("list_partitions", query)

    async def find_optimizer(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: str,
    ) -> TableOptimizer | None:
        def query(connection: Any) -> TableOptimizer | None:
            record = _optimizer(
                connection,
                catalog_id,
                database_name,
                table_name,
                optimizer_type,
            )
            return None if record is None else record[1]

        return await self._read(
            "find_optimizer",
            query,
        )

    async def list_optimizers_for_database(
        self,
        catalog_id: str,
        database_name: str,
    ) -> tuple[TableOptimizer, ...]:
        return await self._read(
            "list_optimizers_for_database",
            lambda connection: _optimizers_from_rows(
                connection,
                connection.execute(
                    _OPTIMIZER_SELECT + " WHERE d.catalog_id = ? AND d.name = ? "
                    "ORDER BY t.name, o.optimizer_type",
                    (catalog_id, database_name),
                ).fetchall(),
            ),
        )

    async def list_optimizers_for_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> tuple[TableOptimizer, ...]:
        return await self._read(
            "list_optimizers_for_table",
            lambda connection: _optimizers_from_rows(
                connection,
                connection.execute(
                    _OPTIMIZER_SELECT + " WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? "
                    "ORDER BY o.optimizer_type",
                    (catalog_id, database_name, table_name),
                ).fetchall(),
            ),
        )

    async def list_active_optimizers(self) -> tuple[TableOptimizer, ...]:
        return await self._read(
            "list_active_optimizers",
            lambda connection: tuple(
                value
                for value in _optimizers_from_rows(
                    connection,
                    connection.execute(
                        _OPTIMIZER_SELECT
                        + " ORDER BY d.catalog_id, d.name, t.name, o.optimizer_type"
                    ).fetchall(),
                )
                if value.active_run is not None
            ),
        )

    async def list_due_optimizers(
        self,
        now: float,
        maximum: int,
    ) -> tuple[TableOptimizer, ...]:
        if maximum <= 0:
            return ()
        return await self._read(
            "list_due_optimizers",
            lambda connection: _optimizers_from_rows(
                connection,
                connection.execute(
                    _OPTIMIZER_SELECT
                    + " WHERE o.next_run_time IS NOT NULL AND o.next_run_time <= ? "
                    "AND json_extract(o.configuration_json, '$.enabled') = 1 "
                    "ORDER BY d.catalog_id, d.name, t.name, o.optimizer_type LIMIT ?",
                    (now, maximum),
                ).fetchall(),
            ),
        )

    @asynccontextmanager
    async def transaction(
        self,
        *,
        operation: str,
        resource_key: CatalogResourceKey,
    ) -> AsyncIterator[CatalogTransaction]:
        await self.initialize()
        connection = await self._begin_write_transaction(operation, resource_key)
        transaction = _SqliteCatalogTransaction(connection)
        try:
            yield transaction
        except BaseException:
            _rollback(connection)
            log_event(
                _LOGGER,
                logging.INFO,
                "glue.sqlite_catalog.transaction.rolled_back",
                operation=operation,
                resource_fingerprint=_resource_fingerprint(resource_key),
                mutated=transaction.mutated,
                side_effect=True,
            )
            raise
        else:
            commit = asyncio.create_task(
                self._commit(
                    connection,
                    transaction,
                    operation=operation,
                    resource_key=resource_key,
                )
            )
            try:
                await asyncio.shield(commit)
            except asyncio.CancelledError:
                try:
                    await commit
                except Exception:
                    raise
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "glue.sqlite_catalog.transaction.cancelled_after_commit",
                    operation=operation,
                    resource_fingerprint=_resource_fingerprint(resource_key),
                    mutated=transaction.mutated,
                    side_effect=True,
                )
                raise
        finally:
            connection.close()

    async def _read(self, category: str, query: Callable[[Any], _Result]) -> _Result:
        await self.initialize()
        started = time.monotonic()
        connection = self._connections.connect()
        try:
            result = query(connection)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.sqlite_catalog.query.failed",
                query_category=category,
                duration_ms=_duration_ms(started),
                fix_hint=(
                    "Inspect the application query handler for Glue error ordering and the "
                    "SQLite catalog adapter query mapping for storage diagnostics."
                ),
                exc_info=True,
            )
            raise
        finally:
            connection.close()
        log_event(
            _LOGGER,
            logging.DEBUG,
            "glue.sqlite_catalog.query.after",
            query_category=category,
            duration_ms=_duration_ms(started),
            returned_count=_returned_count(result),
        )
        return result

    async def _begin_write_transaction(
        self,
        operation: str,
        resource_key: CatalogResourceKey,
    ) -> Any:
        attempts = self._settings.retry_limit + 1
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            connection = self._connections.connect()
            try:
                log_event(
                    _LOGGER,
                    logging.DEBUG,
                    "glue.sqlite_catalog.transaction.begin.before",
                    operation=operation,
                    resource_fingerprint=_resource_fingerprint(resource_key),
                    attempt=attempt,
                    side_effect=True,
                )
                connection.execute("BEGIN IMMEDIATE")
            except Exception as error:
                connection.close()
                if _is_busy(error) and attempt < attempts:
                    delay_seconds = min(0.05 * attempt, 0.25)
                    log_event(
                        _LOGGER,
                        logging.WARNING,
                        "glue.sqlite_catalog.transaction.busy.retry",
                        operation=operation,
                        resource_fingerprint=_resource_fingerprint(resource_key),
                        attempt=attempt,
                        retry_limit=self._settings.retry_limit,
                        delay_seconds=delay_seconds,
                        duration_ms=_duration_ms(started),
                        side_effect=True,
                        fix_hint=(
                            "Inspect long-running Glue Catalog writers before increasing "
                            "glue.sqlite.busy_timeout_milliseconds or retry_limit."
                        ),
                    )
                    await asyncio.sleep(delay_seconds)
                    continue
                if _is_busy(error):
                    raise CatalogStorageBusyError(
                        "SQLite catalog writer contention exceeded the configured retry policy"
                    ) from error
                raise
            log_event(
                _LOGGER,
                logging.DEBUG,
                "glue.sqlite_catalog.transaction.begin.after",
                operation=operation,
                resource_fingerprint=_resource_fingerprint(resource_key),
                attempt=attempt,
                duration_ms=_duration_ms(started),
                side_effect=True,
            )
            return connection
        raise AssertionError("SQLite transaction retry loop exhausted unexpectedly")

    async def _commit(
        self,
        connection: Any,
        transaction: _SqliteCatalogTransaction,
        *,
        operation: str,
        resource_key: CatalogResourceKey,
    ) -> None:
        started = time.monotonic()
        try:
            if self._transaction_hook is not None:
                await self._transaction_hook.before_commit(
                    operation=operation,
                    resource_key=resource_key,
                    mutated=transaction.mutated,
                )
            if transaction.mutated:
                connection.execute(
                    "UPDATE catalog_metadata SET state_revision = state_revision + 1, "
                    "updated_at = ? "
                    "WHERE singleton = 1",
                    (self._now(),),
                )
            log_event(
                _LOGGER,
                logging.DEBUG,
                "glue.sqlite_catalog.transaction.commit.before",
                operation=operation,
                resource_fingerprint=_resource_fingerprint(resource_key),
                mutated=transaction.mutated,
                side_effect=True,
            )
            connection.commit()
        except BaseException:
            _rollback(connection)
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.sqlite_catalog.transaction.commit.failed",
                operation=operation,
                resource_fingerprint=_resource_fingerprint(resource_key),
                mutated=transaction.mutated,
                duration_ms=_duration_ms(started),
                side_effect=True,
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.sqlite_catalog.transaction.commit.after",
            operation=operation,
            resource_fingerprint=_resource_fingerprint(resource_key),
            mutated=transaction.mutated,
            duration_ms=_duration_ms(started),
            side_effect=True,
        )


class _SqliteCatalogTransaction:
    """Private typed facade over one immediate SQLite write transaction."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self.mutated = False

    async def find_database(self, catalog_id: str, database_name: str) -> CatalogDatabase | None:
        record = _database(self._connection, catalog_id, database_name)
        return None if record is None else record[1]

    async def list_databases(self, catalog_id: str) -> tuple[CatalogDatabase, ...]:
        rows = self._connection.execute(
            "SELECT catalog_id, name, definition_json, create_time "
            "FROM catalog_databases WHERE catalog_id = ? ORDER BY name",
            (catalog_id,),
        ).fetchall()
        return tuple(database_from_row(tuple(row)) for row in rows)

    async def find_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> CatalogTable | None:
        record = _table(self._connection, catalog_id, database_name, table_name)
        return None if record is None else record[1]

    async def list_tables(
        self,
        catalog_id: str,
        database_name: str,
    ) -> tuple[CatalogTable, ...]:
        rows = self._connection.execute(
            "SELECT t.table_id, d.catalog_id, d.name, t.name, t.definition_json, "
            "t.create_time, t.update_time, t.version_id "
            "FROM catalog_tables AS t JOIN catalog_databases AS d "
            "ON d.database_id = t.database_id "
            "WHERE d.catalog_id = ? AND d.name = ? ORDER BY t.name",
            (catalog_id, database_name),
        ).fetchall()
        return tuple(_table_from_record(self._connection, tuple(row))[1] for row in rows)

    async def find_partition(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
    ) -> CatalogPartition | None:
        record = _partition(self._connection, catalog_id, database_name, table_name, values)
        return None if record is None else record[1]

    async def list_partitions(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> tuple[CatalogPartition, ...]:
        rows = self._connection.execute(
            "SELECT p.partition_id, d.catalog_id, d.name, t.name, p.values_json, "
            "p.definition_json, p.creation_time, p.update_time "
            "FROM catalog_partitions AS p "
            "JOIN catalog_tables AS t ON t.table_id = p.table_id "
            "JOIN catalog_databases AS d ON d.database_id = t.database_id "
            "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ?",
            (catalog_id, database_name, table_name),
        ).fetchall()
        return tuple(
            sorted(
                (partition_from_row(tuple(row[1:])) for row in rows), key=lambda value: value.values
            )
        )

    async def find_optimizer(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: str,
    ) -> TableOptimizer | None:
        record = _optimizer(
            self._connection,
            catalog_id,
            database_name,
            table_name,
            optimizer_type,
        )
        return None if record is None else record[1]

    async def list_optimizers_for_database(
        self,
        catalog_id: str,
        database_name: str,
    ) -> tuple[TableOptimizer, ...]:
        return _optimizers_from_rows(
            self._connection,
            self._connection.execute(
                _OPTIMIZER_SELECT + " WHERE d.catalog_id = ? AND d.name = ? "
                "ORDER BY t.name, o.optimizer_type",
                (catalog_id, database_name),
            ).fetchall(),
        )

    async def list_optimizers_for_table(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
    ) -> tuple[TableOptimizer, ...]:
        return _optimizers_from_rows(
            self._connection,
            self._connection.execute(
                _OPTIMIZER_SELECT + " WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? "
                "ORDER BY o.optimizer_type",
                (catalog_id, database_name, table_name),
            ).fetchall(),
        )

    async def list_active_optimizers(self) -> tuple[TableOptimizer, ...]:
        return tuple(
            value
            for value in _optimizers_from_rows(
                self._connection,
                self._connection.execute(
                    _OPTIMIZER_SELECT + " ORDER BY d.catalog_id, d.name, t.name, o.optimizer_type"
                ).fetchall(),
            )
            if value.active_run is not None
        )

    async def list_due_optimizers(
        self,
        now: float,
        maximum: int,
    ) -> tuple[TableOptimizer, ...]:
        if maximum <= 0:
            return ()
        return _optimizers_from_rows(
            self._connection,
            self._connection.execute(
                _OPTIMIZER_SELECT + " WHERE o.next_run_time IS NOT NULL AND o.next_run_time <= ? "
                "AND json_extract(o.configuration_json, '$.enabled') = 1 "
                "ORDER BY d.catalog_id, d.name, t.name, o.optimizer_type LIMIT ?",
                (now, maximum),
            ).fetchall(),
        )

    async def insert_database(self, value: CatalogDatabase) -> bool:
        try:
            cursor = self._connection.execute(
                "INSERT INTO catalog_databases (catalog_id, name, definition_json, create_time) "
                "VALUES (?, ?, ?, ?)",
                (
                    value.catalog_id,
                    value.name,
                    encode_document(value.definition),
                    value.create_time,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1

    async def replace_database(
        self,
        current: CatalogDatabase,
        revised: CatalogDatabase,
    ) -> bool:
        try:
            cursor = self._connection.execute(
                "UPDATE catalog_databases SET name = ?, definition_json = ? "
                "WHERE database_id = (SELECT database_id FROM catalog_databases "
                "WHERE catalog_id = ? AND name = ?)",
                (
                    revised.name,
                    encode_document(revised.definition),
                    current.catalog_id,
                    current.name,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1

    async def delete_database(self, value: CatalogDatabase) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM catalog_databases WHERE catalog_id = ? AND name = ?",
            (value.catalog_id, value.name),
        )
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1

    async def insert_table(self, value: CatalogTable) -> bool:
        database = _database(self._connection, value.catalog_id, value.database_name)
        if database is None:
            return False
        try:
            cursor = self._connection.execute(
                "INSERT INTO catalog_tables (database_id, name, definition_json, create_time, "
                "update_time, version_id) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    database[0],
                    value.name,
                    encode_document(value.definition),
                    value.create_time,
                    value.update_time,
                    value.version_id,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        if cursor.rowcount != 1:
            return False
        table_id = int(cursor.lastrowid)
        _replace_partition_keys(self._connection, table_id, value)
        _replace_table_versions(self._connection, table_id, value)
        self.mutated = True
        return True

    async def replace_table(self, current: CatalogTable, revised: CatalogTable) -> bool:
        record = _table(
            self._connection,
            current.catalog_id,
            current.database_name,
            current.name,
        )
        if record is None:
            return False
        table_id = record[0]
        try:
            cursor = self._connection.execute(
                "UPDATE catalog_tables SET name = ?, definition_json = ?, update_time = ?, "
                "version_id = ? WHERE table_id = ? AND version_id = ?",
                (
                    revised.name,
                    encode_document(revised.definition),
                    revised.update_time,
                    revised.version_id,
                    table_id,
                    current.version_id,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        if cursor.rowcount != 1:
            return False
        _replace_partition_keys(self._connection, table_id, revised)
        _replace_table_versions(self._connection, table_id, revised)
        self.mutated = True
        return True

    async def delete_table(self, value: CatalogTable) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM catalog_tables WHERE table_id = ("
            "SELECT t.table_id FROM catalog_tables AS t JOIN catalog_databases AS d "
            "ON d.database_id = t.database_id "
            "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ?)",
            (value.catalog_id, value.database_name, value.name),
        )
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1

    async def insert_partition(self, value: CatalogPartition) -> bool:
        table = _table(
            self._connection,
            value.catalog_id,
            value.database_name,
            value.table_name,
        )
        if table is None:
            return False
        values_key = partition_values_key(value.values)
        try:
            cursor = self._connection.execute(
                "INSERT INTO catalog_partitions ("
                "table_id, values_key, values_json, definition_json, "
                "creation_time, update_time) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    table[0],
                    values_key,
                    encode_document(list(value.values)),
                    encode_document(value.definition),
                    value.creation_time,
                    value.update_time,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        if cursor.rowcount != 1:
            return False
        _replace_partition_values(self._connection, int(cursor.lastrowid), value.values)
        self.mutated = True
        return True

    async def replace_partition(
        self,
        current: CatalogPartition,
        revised: CatalogPartition,
    ) -> bool:
        record = _partition(
            self._connection,
            current.catalog_id,
            current.database_name,
            current.table_name,
            current.values,
        )
        if record is None:
            return False
        partition_id = record[0]
        try:
            cursor = self._connection.execute(
                "UPDATE catalog_partitions SET values_key = ?, values_json = ?, "
                "definition_json = ?, "
                "update_time = ? WHERE partition_id = ?",
                (
                    partition_values_key(revised.values),
                    encode_document(list(revised.values)),
                    encode_document(revised.definition),
                    revised.update_time,
                    partition_id,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        if cursor.rowcount != 1:
            return False
        _replace_partition_values(self._connection, partition_id, revised.values)
        self.mutated = True
        return True

    async def delete_partition(self, value: CatalogPartition) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM catalog_partitions WHERE partition_id = ("
            "SELECT p.partition_id FROM catalog_partitions AS p "
            "JOIN catalog_tables AS t ON t.table_id = p.table_id "
            "JOIN catalog_databases AS d ON d.database_id = t.database_id "
            "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? AND p.values_key = ?)",
            (
                value.catalog_id,
                value.database_name,
                value.table_name,
                partition_values_key(value.values),
            ),
        )
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1

    async def insert_optimizer(self, value: TableOptimizer) -> bool:
        table = _table(
            self._connection,
            value.catalog_id,
            value.database_name,
            value.table_name,
        )
        if table is None:
            return False
        try:
            cursor = self._connection.execute(
                "INSERT INTO catalog_table_optimizers ("
                "table_id, optimizer_type, configuration_json, "
                "create_time, update_time, next_run_time, revision, consecutive_failures) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    table[0],
                    value.optimizer_type.value,
                    encode_document(value.configuration.document),
                    value.create_time,
                    value.update_time,
                    value.next_run_time,
                    value.revision,
                    value.consecutive_failures,
                ),
            )
        except Exception as error:
            if _is_integrity(error):
                return False
            raise
        if cursor.rowcount != 1:
            return False
        _replace_optimizer_runs(self._connection, int(cursor.lastrowid), value)
        self.mutated = True
        return True

    async def replace_optimizer(
        self,
        current: TableOptimizer,
        revised: TableOptimizer,
    ) -> bool:
        record = _optimizer(
            self._connection,
            current.catalog_id,
            current.database_name,
            current.table_name,
            current.optimizer_type.value,
        )
        if record is None:
            return False
        optimizer_id = record[0]
        cursor = self._connection.execute(
            "UPDATE catalog_table_optimizers SET configuration_json = ?, update_time = ?, "
            "next_run_time = ?, revision = ?, consecutive_failures = ? "
            "WHERE optimizer_id = ? AND revision = ?",
            (
                encode_document(revised.configuration.document),
                revised.update_time,
                revised.next_run_time,
                revised.revision,
                revised.consecutive_failures,
                optimizer_id,
                current.revision,
            ),
        )
        if cursor.rowcount != 1:
            return False
        _replace_optimizer_runs(self._connection, optimizer_id, revised)
        self.mutated = True
        return True

    async def delete_optimizer(self, value: TableOptimizer) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM catalog_table_optimizers WHERE optimizer_id = ("
            "SELECT o.optimizer_id FROM catalog_table_optimizers AS o "
            "JOIN catalog_tables AS t ON t.table_id = o.table_id "
            "JOIN catalog_databases AS d ON d.database_id = t.database_id "
            "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? AND o.optimizer_type = ?)",
            (
                value.catalog_id,
                value.database_name,
                value.table_name,
                value.optimizer_type.value,
            ),
        )
        self.mutated = self.mutated or cursor.rowcount == 1
        return cursor.rowcount == 1


def _database(
    connection: Any,
    catalog_id: str,
    database_name: str,
) -> tuple[int, CatalogDatabase] | None:
    row = connection.execute(
        "SELECT database_id, catalog_id, name, definition_json, create_time "
        "FROM catalog_databases WHERE catalog_id = ? AND name = ?",
        (catalog_id, database_name),
    ).fetchone()
    if row is None:
        return None
    return int(row[0]), database_from_row(tuple(row[1:]))


def _table(
    connection: Any,
    catalog_id: str,
    database_name: str,
    table_name: str,
) -> tuple[int, CatalogTable] | None:
    row = connection.execute(
        "SELECT t.table_id, d.catalog_id, d.name, t.name, t.definition_json, "
        "t.create_time, t.update_time, t.version_id "
        "FROM catalog_tables AS t JOIN catalog_databases AS d "
        "ON d.database_id = t.database_id "
        "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ?",
        (catalog_id, database_name, table_name),
    ).fetchone()
    if row is None:
        return None
    return _table_from_record(connection, tuple(row))


def _table_from_record(connection: Any, row: tuple[Any, ...]) -> tuple[int, CatalogTable]:
    table_id = int(row[0])
    archived = connection.execute(
        "SELECT archive_sequence, version_id, definition_json, create_time, update_time "
        "FROM catalog_table_versions WHERE table_id = ? ORDER BY archive_sequence",
        (table_id,),
    ).fetchall()
    return table_id, table_from_row(tuple(row[1:]), (tuple(value) for value in archived))


def _partition(
    connection: Any,
    catalog_id: str,
    database_name: str,
    table_name: str,
    values: tuple[str, ...],
) -> tuple[int, CatalogPartition] | None:
    row = connection.execute(
        "SELECT p.partition_id, d.catalog_id, d.name, t.name, p.values_json, "
        "p.definition_json, p.creation_time, p.update_time "
        "FROM catalog_partitions AS p "
        "JOIN catalog_tables AS t ON t.table_id = p.table_id "
        "JOIN catalog_databases AS d ON d.database_id = t.database_id "
        "WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? AND p.values_key = ?",
        (catalog_id, database_name, table_name, partition_values_key(values)),
    ).fetchone()
    if row is None:
        return None
    return int(row[0]), partition_from_row(tuple(row[1:]))


_OPTIMIZER_SELECT = (
    "SELECT o.optimizer_id, d.catalog_id, d.name, t.name, o.optimizer_type, "
    "o.configuration_json, o.create_time, o.update_time, o.next_run_time, o.revision, "
    "o.consecutive_failures FROM catalog_table_optimizers AS o "
    "JOIN catalog_tables AS t ON t.table_id = o.table_id "
    "JOIN catalog_databases AS d ON d.database_id = t.database_id"
)


def _optimizer(
    connection: Any,
    catalog_id: str,
    database_name: str,
    table_name: str,
    optimizer_type: str,
) -> tuple[int, TableOptimizer] | None:
    row = connection.execute(
        _OPTIMIZER_SELECT
        + " WHERE d.catalog_id = ? AND d.name = ? AND t.name = ? AND o.optimizer_type = ?",
        (catalog_id, database_name, table_name, optimizer_type),
    ).fetchone()
    if row is None:
        return None
    return _optimizer_from_record(connection, tuple(row))


def _optimizer_from_record(connection: Any, row: tuple[Any, ...]) -> tuple[int, TableOptimizer]:
    optimizer_id = int(row[0])
    runs = connection.execute(
        "SELECT run_sequence, run_id, event_type, start_timestamp, end_timestamp, "
        "configuration_json, metrics_json, error "
        "FROM catalog_table_optimizer_runs WHERE optimizer_id = ? ORDER BY run_sequence",
        (optimizer_id,),
    ).fetchall()
    return optimizer_id, optimizer_from_rows(tuple(row[1:]), (tuple(value) for value in runs))


def _optimizers_from_rows(connection: Any, rows: list[Any]) -> tuple[TableOptimizer, ...]:
    return tuple(_optimizer_from_record(connection, tuple(row))[1] for row in rows)


def _replace_partition_keys(connection: Any, table_id: int, value: CatalogTable) -> None:
    connection.execute(
        "DELETE FROM catalog_table_partition_keys WHERE table_id = ?",
        (table_id,),
    )
    for ordinal, raw_json, name, type_name in partition_key_rows(value):
        connection.execute(
            "INSERT INTO catalog_table_partition_keys ("
            "table_id, ordinal, raw_json, name, type_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (table_id, ordinal, raw_json, name, type_name),
        )


def _replace_table_versions(connection: Any, table_id: int, value: CatalogTable) -> None:
    connection.execute(
        "DELETE FROM catalog_table_versions WHERE table_id = ?",
        (table_id,),
    )
    for sequence, version in enumerate(value.archived_versions):
        connection.execute(
            "INSERT INTO catalog_table_versions (table_id, archive_sequence, version_id, "
            "definition_json, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?)",
            (
                table_id,
                sequence,
                version.version_id,
                encode_document(version.definition),
                version.create_time,
                version.update_time,
            ),
        )


def _replace_partition_values(
    connection: Any,
    partition_id: int,
    values: tuple[str, ...],
) -> None:
    connection.execute(
        "DELETE FROM catalog_partition_values WHERE partition_id = ?", (partition_id,)
    )
    connection.executemany(
        "INSERT INTO catalog_partition_values (partition_id, ordinal, value) VALUES (?, ?, ?)",
        ((partition_id, ordinal, value) for ordinal, value in enumerate(values)),
    )


def _replace_optimizer_runs(
    connection: Any,
    optimizer_id: int,
    value: TableOptimizer,
) -> None:
    connection.execute(
        "DELETE FROM catalog_table_optimizer_runs WHERE optimizer_id = ?", (optimizer_id,)
    )
    connection.executemany(
        "INSERT INTO catalog_table_optimizer_runs (optimizer_id, run_sequence, run_id, event_type, "
        "start_timestamp, end_timestamp, configuration_json, metrics_json, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                optimizer_id,
                sequence,
                run.run_id,
                run.event_type.value,
                run.start_timestamp,
                run.end_timestamp,
                None if run.configuration is None else encode_document(run.configuration),
                None if run.metrics is None else encode_document(run.metrics),
                run.error,
            )
            for sequence, run in enumerate(value.runs)
        ),
    )


def _rollback(connection: Any) -> None:
    try:
        connection.rollback()
    except Exception:
        _LOGGER.exception("glue.sqlite_catalog.transaction.rollback.failed")


def _is_busy(error: BaseException) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in ("database is locked", "database is busy", "locked"))


def _is_integrity(error: BaseException) -> bool:
    message = str(error).lower()
    return "unique constraint" in message or "foreign key constraint" in message


def _resource_fingerprint(resource_key: CatalogResourceKey) -> str:
    return hashlib.sha256(repr(resource_key).encode("utf-8")).hexdigest()[:16]


def _duration_ms(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 3)


def _returned_count(value: object) -> int | None:
    if isinstance(value, tuple):
        return len(value)
    return None
