"""Normalized SQLite schema for the Glue Data Catalog.

Opaque Glue documents remain JSON TEXT for lossless fields. Identity, page ordering, typed
partition projections, and segment assignments are relational so request cost is bounded by a
page instead of the whole catalog.

References:
- https://www.sqlite.org/foreignkeys.html
- https://www.sqlite.org/lang_createtable.html
- https://www.sqlite.org/queryplanner.html
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 3

_METADATA_STATEMENT = """
    CREATE TABLE IF NOT EXISTS catalog_metadata (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        schema_version INTEGER NOT NULL,
        state_revision INTEGER NOT NULL,
        updated_at REAL NOT NULL
    )
"""

_TABLE_STATEMENTS = (
    _METADATA_STATEMENT,
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
        order_key BLOB NOT NULL,
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
    CREATE TABLE IF NOT EXISTS catalog_partition_value_projections (
        partition_id INTEGER NOT NULL REFERENCES catalog_partitions(partition_id) ON DELETE CASCADE,
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL,
        type_family TEXT NOT NULL COLLATE BINARY,
        conversion_valid INTEGER NOT NULL CHECK (conversion_valid IN (0, 1)),
        string_value TEXT,
        date_value TEXT,
        timestamp_value TEXT,
        numeric_value TEXT,
        PRIMARY KEY (partition_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_partition_projection_health (
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        issue_kind TEXT NOT NULL COLLATE BINARY,
        ordinal INTEGER NOT NULL,
        first_order_key BLOB NOT NULL,
        first_partition_id INTEGER NOT NULL REFERENCES catalog_partitions(partition_id)
            ON DELETE CASCADE,
        PRIMARY KEY (table_id, issue_kind, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_partition_segments (
        partition_id INTEGER NOT NULL REFERENCES catalog_partitions(partition_id) ON DELETE CASCADE,
        table_id INTEGER NOT NULL REFERENCES catalog_tables(table_id) ON DELETE CASCADE,
        total_segments INTEGER NOT NULL CHECK (total_segments BETWEEN 1 AND 10),
        segment_number INTEGER NOT NULL,
        PRIMARY KEY (partition_id, total_segments)
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
)

_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS catalog_tables_database_name ON catalog_tables(database_id, name)",
    "CREATE INDEX IF NOT EXISTS catalog_partitions_table_values "
    "ON catalog_partitions(table_id, values_key)",
    "CREATE INDEX IF NOT EXISTS catalog_partitions_page "
    "ON catalog_partitions(table_id, order_key, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_values_partition "
    "ON catalog_partition_values(partition_id, ordinal)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_values_ordinal_value "
    "ON catalog_partition_values(ordinal, value, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_projection_text "
    "ON catalog_partition_value_projections("
    "table_id, ordinal, type_family, conversion_valid, string_value COLLATE BINARY, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_projection_date "
    "ON catalog_partition_value_projections("
    "table_id, ordinal, type_family, conversion_valid, date_value COLLATE BINARY, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_projection_timestamp "
    "ON catalog_partition_value_projections("
    "table_id, ordinal, type_family, conversion_valid, timestamp_value COLLATE BINARY, "
    "partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_projection_numeric "
    "ON catalog_partition_value_projections("
    "table_id, ordinal, type_family, conversion_valid, "
    "numeric_value COLLATE MYSTACK_NUMERIC, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_projection_health_lookup "
    "ON catalog_partition_projection_health(table_id, issue_kind, ordinal)",
    "CREATE INDEX IF NOT EXISTS catalog_partition_segments_lookup "
    "ON catalog_partition_segments(table_id, total_segments, segment_number, partition_id)",
    "CREATE INDEX IF NOT EXISTS catalog_optimizers_table_type "
    "ON catalog_table_optimizers(table_id, optimizer_type)",
    "CREATE INDEX IF NOT EXISTS catalog_optimizers_due "
    "ON catalog_table_optimizers(next_run_time, optimizer_id)",
    "CREATE INDEX IF NOT EXISTS catalog_optimizer_runs_order "
    "ON catalog_table_optimizer_runs(optimizer_id, run_sequence)",
)


def initialize_schema(connection: Any, *, now: float) -> None:
    """Create/validate the only supported catalog schema inside one immediate transaction.

    Mystack deliberately has no legacy JSON importer or implicit schema migration. A version-1
    SQLite file must be backed up and recreated before it can be mounted by the version-3 query
    projection runtime; failing closed avoids silently changing a catalog under a live client.
    """

    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(_METADATA_STATEMENT)
        row = connection.execute(
            "SELECT schema_version FROM catalog_metadata WHERE singleton = 1"
        ).fetchone()
        if row is not None and int(row[0]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported Glue SQLite catalog schema {row[0]!r}; expected {SCHEMA_VERSION}. "
                "Back up and recreate the catalog database; Mystack does not perform an implicit "
                "catalog migration."
            )
        for statement in _TABLE_STATEMENTS:
            connection.execute(statement)
        for statement in _INDEX_STATEMENTS:
            connection.execute(statement)
        if row is None:
            connection.execute(
                "INSERT INTO catalog_metadata ("
                "singleton, schema_version, state_revision, updated_at) "
                "VALUES (1, ?, 0, ?)",
                (SCHEMA_VERSION, now),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
