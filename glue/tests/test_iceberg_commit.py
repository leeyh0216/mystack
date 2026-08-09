"""Focused Iceberg GlueCatalog commit and SQLite writer-contention contracts.

References:
- https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking
- https://www.sqlite.org/lang_transaction.html
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import sqlite3
from pathlib import Path
from queue import Empty
from typing import Any

import pytest
from mystack.aws_protocol import load_configuration
from mystack.glue.adapters.outbound import SqliteCatalogRepository
from mystack.glue.adapters.outbound.sqlite_catalog.repository import CatalogStorageBusyError
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)
from mystack.glue.config import GlueSettings
from mystack.glue.domain import VersionMismatchError

from test_support.glue_error_harness import (
    IncrementingIdentifierGenerator,
    InMemoryIcebergMetadataStore,
)


class IncrementingClock:
    def __init__(self) -> None:
        self._value = 0.0

    def now(self) -> float:
        self._value += 1.0
        return self._value


def _settings(
    database_file: Path,
    *,
    busy_timeout_milliseconds: int = 250,
) -> SQLiteRuntimeSettings:
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
        busy_timeout_milliseconds=busy_timeout_milliseconds,
        retry_limit=0,
        checkpoint=SQLiteCheckpointSettings(mode="passive", auto_checkpoint_pages=1000),
    )


def _application(
    database_file: Path,
    *,
    busy_timeout_milliseconds: int = 250,
) -> CatalogApplication:
    catalog = SqliteCatalogRepository(
        _settings(database_file, busy_timeout_milliseconds=busy_timeout_milliseconds)
    )
    return CatalogApplication(
        catalog,
        catalog,
        catalog,
        IncrementingClock(),
        CatalogPolicy(
            default_catalog_id="account",
            api_page_size=100,
            create_default_database=False,
            partition_expressions=PartitionExpressionPolicy(
                max_length=2048,
                max_tokens=512,
                supported_key_types=("string",),
            ),
        ),
        iceberg_metadata_store=InMemoryIcebergMetadataStore(),
        identifier_generator=IncrementingIdentifierGenerator(),
    )


def _definition(writer: str, metadata_name: str) -> dict[str, Any]:
    return {
        "Name": "events",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": f"s3://warehouse/events/metadata/{metadata_name}.json",
            "format": "iceberg/parquet",
            "writer": writer,
        },
        "StorageDescriptor": {
            "Location": "s3://warehouse/events",
            "Columns": [{"Name": "id", "Type": "bigint"}],
        },
    }


async def _seed(database_file: Path) -> None:
    application = _application(database_file)
    await application.create_database("account", {"Name": "analytics"})
    await application.create_table("account", "analytics", _definition("seed", "v0"))


def _commit_worker(
    database_file: str,
    writer: str,
    start: Any,
    ready: Any,
    results: Any,
) -> None:
    async def commit() -> None:
        application = _application(Path(database_file))
        ready.put(writer)
        if not start.wait(_test_timeout()):
            results.put(("timeout", writer))
            return
        try:
            await application.update_table(
                "account",
                "analytics",
                "events",
                _definition(writer, f"v1-{writer}"),
                version_id="0",
                skip_archive=False,
            )
        except VersionMismatchError:
            results.put(("conflict", writer))
        except BaseException as error:
            results.put(("error", writer, type(error).__name__, str(error)))
        else:
            results.put(("success", writer))

    asyncio.run(commit())


async def test_interprocess_same_base_commit_has_one_winner_and_no_lost_update(
    tmp_path: Path,
) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    await _seed(database_file)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    results = context.Queue()
    processes = [
        context.Process(
            target=_commit_worker,
            args=(str(database_file), writer, start, ready, results),
        )
        for writer in ("one", "two")
    ]

    for process in processes:
        process.start()
    try:
        assert {ready.get(timeout=_test_timeout()) for _ in processes} == {"one", "two"}
        start.set()
        outcomes = [results.get(timeout=_test_timeout()) for _ in processes]
        assert sorted(value[0] for value in outcomes) == ["conflict", "success"]
    except Empty:
        pytest.fail("Iceberg contention worker exceeded MYSTACK_TEST_TIMEOUT_SECONDS")
    finally:
        for process in processes:
            process.join(timeout=_test_timeout())
            if process.is_alive():
                process.terminate()
                process.join(timeout=_test_timeout())

    assert all(process.exitcode == 0 for process in processes)
    winner = next(value[1] for value in outcomes if value[0] == "success")
    table = await _application(database_file).get_table("account", "analytics", "events")
    assert table.version_id == "1"
    assert table.definition["Parameters"] == _definition(winner, f"v1-{winner}")["Parameters"]
    assert [version.version_id for version in table.archived_versions] == ["0"]
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT state_revision FROM catalog_metadata").fetchone()[0] == 3


async def test_archive_policy_and_stale_failure_preserve_committed_metadata(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    await _seed(database_file)
    application = _application(database_file)

    with caplog.at_level(logging.INFO, logger="mystack.glue.application.iceberg_commit"):
        await application.update_table(
            "account",
            "analytics",
            "events",
            _definition("one", "v1"),
            version_id="0",
            skip_archive=False,
        )
        with pytest.raises(VersionMismatchError):
            await application.update_table(
                "account",
                "analytics",
                "events",
                _definition("stale", "stale"),
                version_id="0",
                skip_archive=False,
            )
    await application.update_table(
        "account",
        "analytics",
        "events",
        _definition("two", "v2"),
        version_id="1",
        skip_archive=True,
    )

    table = await application.get_table("account", "analytics", "events")
    assert table.version_id == "2"
    assert [version.version_id for version in table.archived_versions] == ["0"]
    assert all(
        version.definition["Parameters"]["writer"] != "stale" for version in table.versions()
    )
    commit_events = {record.getMessage() for record in caplog.records}
    assert {
        "glue.iceberg.commit.begin",
        "glue.iceberg.commit.version.accepted",
        "glue.iceberg.commit.persist.before",
        "glue.iceberg.commit.conflict",
        "glue.iceberg.commit.succeeded",
    } <= commit_events


async def test_sqlite_writer_busy_wait_is_bounded(tmp_path: Path) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    await _seed(database_file)
    blocked_application = _application(database_file, busy_timeout_milliseconds=20)
    lock = sqlite3.connect(database_file, timeout=0.01, isolation_level=None)
    lock.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(CatalogStorageBusyError):
            await blocked_application.create_database("account", {"Name": "blocked"})
    finally:
        lock.rollback()
        lock.close()


def test_sqlite_configuration_resolves_database_file() -> None:
    settings = GlueSettings.from_configuration(load_configuration("config/mystack.yaml"))
    assert settings.sqlite.database_file == Path("/var/lib/mystack/glue/catalog.sqlite3")
    assert settings.sqlite.busy_timeout_milliseconds == 5000
    assert settings.object_store.endpoint_url == "http://localstack:4566"
    assert settings.object_store.s3_path_style is True


def _test_timeout() -> float:
    return float(os.getenv("MYSTACK_TEST_TIMEOUT_SECONDS", "10"))
