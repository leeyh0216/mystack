"""Direct SQLite query-pushdown contracts for Glue Catalog list operations.

The existing evaluator remains the semantic oracle. These tests assert that the normal Catalog
path reads one keyset page in SQLite rather than first materializing all catalog rows.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html
- https://www.sqlite.org/queryplanner.html
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from mystack.glue.adapters.outbound.sqlite_catalog.connection import SqliteCatalogConnectionFactory
from mystack.glue.adapters.outbound.sqlite_catalog.keys import partition_order_key
from mystack.glue.adapters.outbound.sqlite_catalog.query_compiler import (
    SqlitePartitionQueryCompiler,
)
from mystack.glue.adapters.outbound.sqlite_catalog.repository import SqliteCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import (
    PartitionExpressionCompiler,
    PartitionExpressionPolicy,
    PartitionKey,
)
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)
from mystack.glue.domain import InvalidInputError

from test_support.glue_error_harness import (
    IncrementingClock,
    IncrementingIdentifierGenerator,
    InMemoryIcebergMetadataStore,
)

_SUPPORTED_TYPES = (
    "string",
    "date",
    "timestamp",
    "int",
    "bigint",
    "long",
    "tinyint",
    "smallint",
    "decimal",
)


class RecordingConnectionFactory:
    """Record SQLite statement shape without changing application query behavior."""

    def __init__(self, settings: SQLiteRuntimeSettings) -> None:
        self._delegate = SqliteCatalogConnectionFactory(settings)
        self.statements: list[str] = []

    def connect(self) -> Any:
        connection = self._delegate.connect()
        connection.set_trace_callback(self.statements.append)
        return connection

    def clear(self) -> None:
        self.statements.clear()


def _settings(database_file: Path) -> SQLiteRuntimeSettings:
    return SQLiteRuntimeSettings(
        database_file=database_file,
        driver=SQLiteDriverSettings(
            module="sqlite3",
            expected_version="3.53.4",
            minimum_wal_version="3.51.3",
            manifest_file=database_file.with_name("unused-runtime-manifest.json"),
        ),
        journal_mode="rollback",
        synchronous="full",
        busy_timeout_milliseconds=250,
        retry_limit=0,
        checkpoint=SQLiteCheckpointSettings(mode="passive", auto_checkpoint_pages=1000),
    )


def _application(
    database_file: Path,
) -> tuple[CatalogApplication, RecordingConnectionFactory]:
    settings = _settings(database_file)
    connections = RecordingConnectionFactory(settings)
    catalog = SqliteCatalogRepository(settings, connection_factory=connections)
    application = CatalogApplication(
        catalog,
        catalog,
        catalog,
        IncrementingClock(),
        CatalogPolicy(
            default_catalog_id="account",
            api_page_size=100,
            create_default_database=False,
            partition_expressions=PartitionExpressionPolicy(2048, 512, _SUPPORTED_TYPES),
        ),
        iceberg_metadata_store=InMemoryIcebergMetadataStore(),
        identifier_generator=IncrementingIdentifierGenerator(),
    )
    return application, connections


async def _create_partition_table(
    application: CatalogApplication,
    *,
    database_name: str = "analytics",
    table_name: str = "events",
    partition_keys: list[dict[str, str]] | None = None,
) -> None:
    await application.create_database("account", {"Name": database_name})
    await application.create_table(
        "account",
        database_name,
        {
            "Name": table_name,
            "StorageDescriptor": {"Columns": []},
            "PartitionKeys": partition_keys
            or [
                {"Name": "year", "Type": "int"},
                {"Name": "region", "Type": "string"},
                {"Name": "day", "Type": "date"},
            ],
        },
    )


def _decoded_token(token: str) -> dict[str, object]:
    padded = token + "=" * (-len(token) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))


def test_partition_order_key_preserves_python_tuple_order() -> None:
    values = [
        ("a", "z"),
        ("a\x00", "a"),
        ("a\x00x", "a"),
        ("a\U0001f600", "a"),
        ("b", "a"),
    ]

    assert sorted(values) == sorted(values, key=partition_order_key)


def test_partition_sql_compiler_uses_only_ordinal_sql_and_bound_literals() -> None:
    compiler = PartitionExpressionCompiler(PartitionExpressionPolicy(2048, 512, _SUPPORTED_TYPES))
    bound = compiler.compile(
        "`release day` IN ('it''s-ready', 'ship--it') OR NOT region LIKE 'private-.*'",
        (PartitionKey("release day", "string"), PartitionKey("region", "string")),
    )

    compiled = SqlitePartitionQueryCompiler().compile(bound)

    assert "release day" not in compiled.predicate_sql
    assert "ship--it" not in compiled.predicate_sql
    assert "private-" not in compiled.predicate_sql
    assert "pv_0" in " ".join(compiled.joins)
    assert "mystack_glue_like" in compiled.predicate_sql
    assert "it's-ready" in compiled.parameters
    assert "ship--it" in compiled.parameters


async def test_database_and_table_pages_use_name_order_and_indexed_keysets(tmp_path: Path) -> None:
    application, connections = _application(tmp_path / "catalog.sqlite3")
    for database_name in ("zeta", "alpha", "beta"):
        await application.create_database("account", {"Name": database_name})
    for table_name in ("zeta_events", "alpha_events", "beta_events"):
        await application.create_table(
            "account",
            "alpha",
            {"Name": table_name, "StorageDescriptor": {"Columns": []}},
        )

    connections.clear()
    first_databases, database_token = await application.get_databases(
        "account", next_token=None, max_results=1
    )
    second_databases, _ = await application.get_databases(
        "account", next_token=database_token, max_results=1
    )

    assert [value.name for value in first_databases + second_databases] == ["alpha", "beta"]
    assert database_token is not None
    database_statements = "\n".join(connections.statements)
    assert "ORDER BY name COLLATE BINARY, database_id LIMIT 2" in database_statements
    assert " OFFSET " not in database_statements.upper()

    with pytest.raises(InvalidInputError, match="does not match"):
        await application.get_tables(
            "account",
            "alpha",
            expression=None,
            next_token=database_token,
            max_results=1,
        )

    connections.clear()
    first_tables, table_token = await application.get_tables(
        "account",
        "alpha",
        expression="_events$",
        next_token=None,
        max_results=1,
    )
    second_tables, _ = await application.get_tables(
        "account",
        "alpha",
        expression="_events$",
        next_token=table_token,
        max_results=1,
    )

    assert [value.name for value in first_tables + second_tables] == [
        "alpha_events",
        "beta_events",
    ]
    assert "ORDER BY t.name COLLATE BINARY, t.table_id LIMIT 2" in "\n".join(connections.statements)


async def test_partition_pushdown_matches_evaluator_and_reads_only_a_keyset_page(
    tmp_path: Path,
) -> None:
    application, connections = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(application)
    values = (
        ("2025", "us-east-1", "2025-12-31"),
        ("2026", "ap-northeast-2", "2026-08-08"),
        ("2026", "ap-southeast-1", "2026-08-09"),
        ("2027", "eu-west-1", "2027-01-01"),
    )
    for value in values:
        await application.create_partition(
            "account", "analytics", "events", {"Values": list(value)}
        )

    expression = "year BETWEEN 2026 AND 2027 AND region LIKE 'ap-.*' AND NOT day < '2026-08-08'"
    compiler = PartitionExpressionCompiler(PartitionExpressionPolicy(2048, 512, _SUPPORTED_TYPES))
    predicate = compiler.compile(
        expression,
        (
            PartitionKey("year", "int"),
            PartitionKey("region", "string"),
            PartitionKey("day", "date"),
        ),
    )
    expected = [value for value in sorted(values) if predicate.matches(value)]

    connections.clear()
    first, token = await application.get_partitions(
        "account",
        "analytics",
        "events",
        expression=expression,
        segment=None,
        next_token=None,
        max_results=1,
    )
    second, second_token = await application.get_partitions(
        "account",
        "analytics",
        "events",
        expression=expression,
        segment=None,
        next_token=token,
        max_results=1,
    )

    assert [value.values for value in first + second] == expected
    assert second_token is None
    assert token is not None
    assert _decoded_token(token).keys() == {"v", "c", "i"}
    assert all("ap-northeast-2" not in str(value) for value in _decoded_token(token).values())
    statements = "\n".join(connections.statements)
    assert "catalog_partition_value_projections AS pv_0" in statements
    assert "catalog_partition_segments" not in statements
    assert "ORDER BY p.order_key, p.partition_id LIMIT 2" in statements
    assert " OFFSET " not in statements.upper()
    assert "COUNT(" not in statements.upper()


async def test_supported_partition_expression_forms_match_the_evaluator(tmp_path: Path) -> None:
    application, _ = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(application)
    values = (
        ("2025", "us-east-1", "2025-12-31"),
        ("2026", "ap-northeast-2", "2026-08-08"),
        ("2026", "ap-southeast-1", "2026-08-09"),
        ("2027", "eu-west-1", "2027-01-01"),
    )
    for value in values:
        await application.create_partition(
            "account", "analytics", "events", {"Values": list(value)}
        )
    keys = (
        PartitionKey("year", "int"),
        PartitionKey("region", "string"),
        PartitionKey("day", "date"),
    )
    compiler = PartitionExpressionCompiler(PartitionExpressionPolicy(2048, 512, _SUPPORTED_TYPES))

    for expression in (
        "year IN (2025, 2027) OR region = 'ap-southeast-1'",
        "year NOT IN (2025) AND day NOT BETWEEN '2026-08-09' AND '2026-12-31'",
        "NOT (region LIKE 'us-%' OR day < '2026-08-08')",
    ):
        predicate = compiler.compile(expression, keys)
        expected = [value for value in sorted(values) if predicate.matches(value)]
        actual, token = await application.get_partitions(
            "account",
            "analytics",
            "events",
            expression=expression,
            segment=None,
            next_token=None,
            max_results=100,
        )
        assert token is None
        assert [value.values for value in actual] == expected


async def test_partition_segments_are_persisted_and_union_without_duplicate_rows(
    tmp_path: Path,
) -> None:
    application, _ = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(application)
    values = tuple(("2026", f"ap-region-{index}", f"2026-08-{index + 1:02d}") for index in range(6))
    for value in values:
        await application.create_partition(
            "account", "analytics", "events", {"Values": list(value)}
        )

    pages: list[set[tuple[str, ...]]] = []
    for segment_number in range(3):
        response, token = await application.get_partitions(
            "account",
            "analytics",
            "events",
            expression="year = 2026",
            segment=(segment_number, 3),
            next_token=None,
            max_results=100,
        )
        assert token is None
        pages.append({value.values for value in response})

    assert pages[0].isdisjoint(pages[1])
    assert pages[0].isdisjoint(pages[2])
    assert pages[1].isdisjoint(pages[2])
    assert set().union(*pages) == set(values)


async def test_table_partition_key_change_rebuilds_projection_and_reports_later_invalid_values(
    tmp_path: Path,
) -> None:
    application, _ = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(
        application,
        partition_keys=[{"Name": "day", "Type": "string"}],
    )
    await application.create_partition("account", "analytics", "events", {"Values": ["2026-08-08"]})
    await application.create_partition("account", "analytics", "events", {"Values": ["not-a-date"]})
    await application.update_table(
        "account",
        "analytics",
        "events",
        {
            "Name": "events",
            "StorageDescriptor": {"Columns": []},
            "PartitionKeys": [{"Name": "day", "Type": "date"}],
        },
        version_id="0",
        skip_archive=False,
    )

    with pytest.raises(InvalidInputError, match="not valid for key type 'date'"):
        await application.get_partitions(
            "account",
            "analytics",
            "events",
            expression="day >= '2026-08-01'",
            segment=None,
            next_token=None,
            max_results=10,
        )


async def test_table_update_without_partition_key_change_does_not_rebuild_all_projections(
    tmp_path: Path,
) -> None:
    application, connections = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(
        application,
        partition_keys=[{"Name": "day", "Type": "string"}],
    )
    for value in ("2026-08-08", "2026-08-09"):
        await application.create_partition("account", "analytics", "events", {"Values": [value]})

    connections.clear()
    await application.update_table(
        "account",
        "analytics",
        "events",
        {
            "Name": "events",
            "Parameters": {"metadata_location": "s3://warehouse/events/metadata/v2.json"},
            "StorageDescriptor": {"Columns": []},
            "PartitionKeys": [{"Name": "day", "Type": "string"}],
        },
        version_id="0",
        skip_archive=False,
    )

    statements = "\n".join(connections.statements)
    assert "SELECT partition_id, values_json FROM catalog_partitions" not in statements
    assert "DELETE FROM catalog_partition_value_projections" not in statements
    assert "DELETE FROM catalog_partition_segments" not in statements


async def test_empty_table_preserves_lazy_literal_conversion_behavior(tmp_path: Path) -> None:
    application, _ = _application(tmp_path / "catalog.sqlite3")
    await _create_partition_table(
        application,
        partition_keys=[{"Name": "day", "Type": "date"}],
    )

    values, token = await application.get_partitions(
        "account",
        "analytics",
        "events",
        expression="day > 'not-a-date'",
        segment=None,
        next_token=None,
        max_results=10,
    )

    assert values == []
    assert token is None
