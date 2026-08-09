"""Normalized SQLite schema for the Glue Data Catalog.

Opaque Glue documents remain JSON TEXT for lossless fields, while identity, history, and parent
relationships are relational so rename/cascade behavior does not depend on rewriting child rows.

References:
- https://www.sqlite.org/foreignkeys.html
- https://www.sqlite.org/lang_createtable.html
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1

_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS catalog_metadata (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        schema_version INTEGER NOT NULL,
        state_revision INTEGER NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_databases (
        database_id INTEGER PRIMARY KEY,
        catalog_id TEXT NOT NULL COLLATE BINARY,
        name TEXT NOT NULL COLLATE BINARY,
        definition_json TEXT NOT NULL,
        create_time REAL NOT NULL,
        UNIQUE (catalog_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_tables (
        table_id INTEGER PRIMARY KEY,
        database_id INTEGER NOT NULL REFERENCES catalog_databases(database_id) ON DELETE CASCADE,
        name TEXT NOT NULL COLLATE BINARY,
        definition_json TEXT NOT NULL,
        create_time REAL NOT NULL,
        update_time REAL NOT NULL,
        version_id TEXT NOT NULL COLLATE BINARY,
        UNIQUE (database_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_table_versions (
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        archive_sequence INTEGER NOT NULL,
        version_id TEXT NOT NULL COLLATE BINARY,
        definition_json TEXT NOT NULL,
        create_time REAL NOT NULL,
        update_time REAL NOT NULL,
        PRIMARY KEY (table_id, archive_sequence),
        UNIQUE (table_id, version_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_table_partition_keys (
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL,
        raw_json TEXT NOT NULL,
        name TEXT NOT NULL COLLATE BINARY,
        type_name TEXT NOT NULL COLLATE BINARY,
        PRIMARY KEY (table_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_partitions (
        partition_id INTEGER PRIMARY KEY,
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        values_key TEXT NOT NULL COLLATE BINARY,
        values_json TEXT NOT NULL,
        definition_json TEXT NOT NULL,
        creation_time REAL NOT NULL,
        update_time REAL NOT NULL,
        UNIQUE (table_id, values_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_partition_values (
        partition_id INTEGER NOT NULL REFERENCES catalog_partitions(partition_id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (partition_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_table_optimizers (
        optimizer_id INTEGER PRIMARY KEY,
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        optimizer_type TEXT NOT NULL COLLATE BINARY,
        configuration_json TEXT NOT NULL,
        create_time REAL NOT NULL,
        update_time REAL NOT NULL,
        next_run_time REAL,
        revision INTEGER NOT NULL,
        consecutive_failures INTEGER NOT NULL,
        UNIQUE (table_id, optimizer_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_table_optimizer_runs (
        optimizer_id INTEGER NOT NULL REFERENCES catalog_table_optimizers(optimizer_id)
            ON DELETE CASCADE,
        run_sequence INTEGER NOT NULL,
        run_id TEXT NOT NULL COLLATE BINARY,
        event_type TEXT NOT NULL COLLATE BINARY,
        start_timestamp REAL NOT NULL,
        end_timestamp REAL,
        configuration_json TEXT,
        metrics_json TEXT,
        error TEXT,
        PRIMARY KEY (optimizer_id, run_sequence),
        UNIQUE (optimizer_id, run_id)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS catalog_tables_database_name "
        "ON catalog_tables(database_id, name)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS catalog_partitions_table_values "
        "ON catalog_partitions(table_id, values_key)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS catalog_partition_values_partition "
        "ON catalog_partition_values(partition_id, ordinal)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS catalog_optimizers_table_type "
        "ON catalog_table_optimizers(table_id, optimizer_type)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS catalog_optimizers_due "
        "ON catalog_table_optimizers(next_run_time, optimizer_id)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS catalog_optimizer_runs_order "
        "ON catalog_table_optimizer_runs(optimizer_id, run_sequence)"
    ),
)


def initialize_schema(connection: Any, *, now: float) -> None:
    """Create/validate the only supported catalog schema inside one immediate transaction."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in _STATEMENTS:
            connection.execute(statement)
        row = connection.execute(
            "SELECT schema_version FROM catalog_metadata WHERE singleton = 1"
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO catalog_metadata ("
                "singleton, schema_version, state_revision, updated_at) "
                "VALUES (1, ?, 0, ?)",
                (SCHEMA_VERSION, now),
            )
        elif int(row[0]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported Glue SQLite catalog schema {row[0]!r}; expected {SCHEMA_VERSION}"
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
