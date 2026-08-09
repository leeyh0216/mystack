"""SQLite-only Glue Catalog durability and transaction contracts.

References:
- https://www.sqlite.org/lang_transaction.html
- https://www.sqlite.org/foreignkeys.html
- https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

import pytest
from mystack.glue.adapters.outbound import SqliteCatalogRepository
from mystack.glue.adapters.outbound.sqlite_catalog import CatalogTransactionHook
from mystack.glue.application import CatalogApplication, CatalogPolicy, TableOptimizerPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)
from mystack.glue.domain import EntityNotFoundError, VersionMismatchError

from tests.support.glue_error_harness import (
    IncrementingIdentifierGenerator,
    InMemoryIcebergMetadataStore,
    ToggleCommitFailpoint,
)


class IncrementingClock:
    def __init__(self) -> None:
        self._value = 0.0

    def now(self) -> float:
        self._value += 1.0
        return self._value


class BlockingCommitHook:
    def __init__(self) -> None:
        self.block = False
        self.started = asyncio.Event()
        self.allow = asyncio.Event()

    async def before_commit(
        self,
        *,
        operation: str,
        resource_key: tuple[object, ...],
        mutated: bool,
    ) -> None:
        del operation, resource_key, mutated
        if self.block:
            self.started.set()
            await self.allow.wait()


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
        retry_limit=1,
        checkpoint=SQLiteCheckpointSettings(mode="passive", auto_checkpoint_pages=1000),
    )


def _application(
    database_file: Path,
    *,
    hook: CatalogTransactionHook | None = None,
) -> CatalogApplication:
    catalog = SqliteCatalogRepository(_settings(database_file), transaction_hook=hook)
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
                supported_key_types=(
                    "string",
                    "date",
                    "timestamp",
                    "int",
                    "bigint",
                    "long",
                    "tinyint",
                    "smallint",
                    "decimal",
                ),
            ),
        ),
        iceberg_metadata_store=InMemoryIcebergMetadataStore(),
        identifier_generator=IncrementingIdentifierGenerator(),
        table_optimizer_policy=TableOptimizerPolicy(
            initial_delay_seconds=0.0,
            compaction_interval_seconds=60.0,
            history_limit=10,
            compaction_failure_limit=4,
        ),
    )


async def _catalog_tree(application: CatalogApplication) -> None:
    await application.create_database("account", {"Name": "db"})
    await application.create_table(
        "account",
        "db",
        {
            "Name": "table",
            "StorageDescriptor": {"Columns": []},
            "PartitionKeys": [{"Name": "day", "Type": "string"}],
        },
    )
    await application.create_partition(
        "account",
        "db",
        "table",
        {"Values": ["2026-08-08"]},
    )


async def test_catalog_survives_restart_using_only_sqlite(tmp_path: Path) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    await _catalog_tree(_application(database_file))

    restarted = _application(database_file)

    assert (await restarted.get_database("account", "db")).definition == {"Name": "db"}
    assert (await restarted.get_table("account", "db", "table")).version_id == "0"
    assert (await restarted.get_partition("account", "db", "table", ("2026-08-08",))).values == (
        "2026-08-08",
    )
    assert database_file.is_file()
    assert not list(tmp_path.glob("*.json"))


async def test_commit_failpoint_rolls_back_visible_and_durable_rows(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    hook = ToggleCommitFailpoint()
    application = _application(database_file, hook=hook)
    await _catalog_tree(application)
    hook.fail = True

    with caplog.at_level(
        logging.ERROR,
        logger="mystack.glue.adapters.outbound.sqlite_catalog.repository",
    ):
        with pytest.raises(OSError, match="deterministic test persistence failure"):
            await application.update_database("account", "db", {"Name": "renamed"})

    assert await application.get_database("account", "db")
    with pytest.raises(EntityNotFoundError):
        await application.get_database("account", "renamed")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM catalog_databases").fetchone()[0] == 1
    assert "glue.sqlite_catalog.transaction.commit.failed" in {
        record.getMessage() for record in caplog.records
    }


async def test_database_and_table_rename_keep_child_identity_and_cascade(tmp_path: Path) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    application = _application(database_file)
    await _catalog_tree(application)
    with sqlite3.connect(database_file) as connection:
        partition_id = connection.execute("SELECT partition_id FROM catalog_partitions").fetchone()[
            0
        ]

    await application.update_database("account", "db", {"Name": "warehouse"})
    await application.update_table(
        "account",
        "warehouse",
        "table",
        {"Name": "events", "PartitionKeys": [{"Name": "day", "Type": "string"}]},
        version_id="0",
        skip_archive=False,
    )

    restarted = _application(database_file)
    assert (await restarted.get_table("account", "warehouse", "events")).version_id == "1"
    assert (
        await restarted.get_partition("account", "warehouse", "events", ("2026-08-08",))
    ).table_name == "events"
    with sqlite3.connect(database_file) as connection:
        assert (
            connection.execute("SELECT partition_id FROM catalog_partitions").fetchone()[0]
            == partition_id
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    await restarted.delete_database("account", "warehouse")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("SELECT COUNT(*) FROM catalog_tables").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM catalog_partitions").fetchone()[0] == 0


async def test_updates_archive_versions_and_reject_stale_compare_and_swap(tmp_path: Path) -> None:
    application = _application(tmp_path / "catalog.sqlite3")
    await _catalog_tree(application)

    results = await asyncio.gather(
        application.update_table(
            "account",
            "db",
            "table",
            {"Name": "table", "Parameters": {"writer": "one"}},
            version_id="0",
            skip_archive=False,
        ),
        application.update_table(
            "account",
            "db",
            "table",
            {"Name": "table", "Parameters": {"writer": "two"}},
            version_id="0",
            skip_archive=False,
        ),
        return_exceptions=True,
    )

    assert sum(value is None for value in results) == 1
    assert sum(isinstance(value, VersionMismatchError) for value in results) == 1
    versions, _ = await application.get_table_versions(
        "account", "db", "table", next_token=None, max_results=None
    )
    assert [value.version_id for value in versions] == ["0", "1"]


async def test_cancelled_commit_finishes_atomically_before_cancellation(tmp_path: Path) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    hook = BlockingCommitHook()
    application = _application(database_file, hook=hook)
    await _catalog_tree(application)
    hook.block = True
    update = asyncio.create_task(application.update_database("account", "db", {"Name": "renamed"}))
    await asyncio.wait_for(hook.started.wait(), timeout=_test_timeout())

    update.cancel()
    hook.allow.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(update, timeout=_test_timeout())

    assert await _application(database_file).get_database("account", "renamed")


async def test_optimizer_runs_survive_restart_and_table_delete_cascades(tmp_path: Path) -> None:
    database_file = tmp_path / "catalog.sqlite3"
    application = _application(database_file)
    await application.create_database("account", {"Name": "db"})
    await application.create_table(
        "account",
        "db",
        {
            "Name": "iceberg",
            "Parameters": {"table_type": "ICEBERG"},
            "StorageDescriptor": {"Location": "s3://warehouse/db/iceberg"},
        },
    )
    await application.create_table_optimizer("account", "db", "iceberg", "compaction", {})
    work = (await application.claim_due_table_optimizer_work(1))[0]
    assert await application.mark_table_optimizer_in_progress(work)
    assert await application.complete_table_optimizer(work, {"NumberOfFilesCompacted": 2})

    restarted = _application(database_file)
    runs, token = await restarted.list_table_optimizer_runs(
        "account", "db", "iceberg", "compaction", next_token=None, max_results=10
    )
    assert token is None
    assert runs[0].metrics == {"NumberOfFilesCompacted": 2}
    await restarted.delete_table("account", "db", "iceberg")
    with sqlite3.connect(database_file) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM catalog_table_optimizers").fetchone()[0] == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM catalog_table_optimizer_runs").fetchone()[0]
            == 0
        )


def _test_timeout() -> float:
    return float(os.environ.get("MYSTACK_TEST_TIMEOUT_SECONDS", "10"))
