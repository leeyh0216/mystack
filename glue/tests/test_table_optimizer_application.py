"""Managed Glue Iceberg optimizer application behavior and aggregate ownership.

Official API: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mystack.glue.adapters.outbound import SqliteCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy, TableOptimizerPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)
from mystack.glue.domain import AlreadyExistsError, EntityNotFoundError, InvalidInputError

from tests.support.glue_error_harness import InMemoryIcebergMetadataStore


class ManualClock:
    def __init__(self) -> None:
        self.value = 100.0

    def now(self) -> float:
        return self.value


class Identifiers:
    def __init__(self) -> None:
        self.value = 0

    def new(self) -> str:
        self.value += 1
        return f"run-{self.value}"


def _application(tmp_path: Path) -> tuple[CatalogApplication, ManualClock]:
    clock = ManualClock()
    database_file = tmp_path / "catalog.sqlite3"
    catalog = SqliteCatalogRepository(
        SQLiteRuntimeSettings(
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
    )
    application = CatalogApplication(
        catalog,
        catalog,
        catalog,
        clock,
        CatalogPolicy(
            default_catalog_id="account",
            api_page_size=1,
            create_default_database=False,
            partition_expressions=PartitionExpressionPolicy(
                max_length=2048,
                max_tokens=512,
                supported_key_types=("string",),
            ),
        ),
        iceberg_metadata_store=InMemoryIcebergMetadataStore(),
        identifier_generator=Identifiers(),
        table_optimizer_policy=TableOptimizerPolicy(
            initial_delay_seconds=0.0,
            compaction_interval_seconds=60.0,
            history_limit=10,
            compaction_failure_limit=4,
        ),
    )
    return application, clock


async def _create_tables(application: CatalogApplication) -> None:
    await application.create_database("account", {"Name": "db"})
    await application.create_table(
        "account",
        "db",
        {
            "Name": "iceberg",
            "Parameters": {
                "table_type": "ICEBERG",
                "metadata_location": "s3://warehouse/db/iceberg/metadata/v1.json",
            },
            "StorageDescriptor": {"Location": "s3://warehouse/db/iceberg"},
        },
    )
    await application.create_table(
        "account",
        "db",
        {"Name": "hive", "StorageDescriptor": {"Location": "s3://warehouse/db/hive"}},
    )


async def test_optimizer_commands_enforce_iceberg_duplicate_and_missing_invariants(
    tmp_path: Path,
) -> None:
    application, _ = _application(tmp_path)
    await _create_tables(application)
    await application.create_table_optimizer(
        "account", "db", "iceberg", "compaction", {"enabled": False}
    )

    with pytest.raises(AlreadyExistsError):
        await application.create_table_optimizer(
            "account", "db", "iceberg", "compaction", {"enabled": False}
        )
    with pytest.raises(InvalidInputError, match="require an Iceberg table"):
        await application.create_table_optimizer(
            "account", "db", "hive", "compaction", {"enabled": False}
        )

    await application.delete_table_optimizer("account", "db", "iceberg", "compaction")
    with pytest.raises(EntityNotFoundError):
        await application.get_table_optimizer("account", "db", "iceberg", "compaction")

    with pytest.raises(InvalidInputError, match="enabled must be a Boolean"):
        await application.create_table_optimizer(
            "account", "missing", "missing", "compaction", {"enabled": "true"}
        )


async def test_optimizer_run_history_moves_and_cascades_with_owning_table(tmp_path: Path) -> None:
    application, clock = _application(tmp_path)
    await _create_tables(application)
    await application.create_table_optimizer(
        "account", "db", "iceberg", "compaction", {"enabled": True}
    )
    work = (await application.claim_due_table_optimizer_work(1))[0]
    assert await application.mark_table_optimizer_in_progress(work)
    clock.value = 101.0
    assert await application.complete_table_optimizer(
        work,
        {"NumberOfFilesCompacted": 2},
    )
    runs, token = await application.list_table_optimizer_runs(
        "account",
        "db",
        "iceberg",
        "compaction",
        next_token=None,
        max_results=1,
    )
    assert token is None
    assert runs[0].metrics == {"NumberOfFilesCompacted": 2}

    await application.update_table_optimizer(
        "account", "db", "iceberg", "compaction", {"enabled": True}
    )
    active_work = (await application.claim_due_table_optimizer_work(1))[0]
    assert await application.mark_table_optimizer_in_progress(active_work)

    table = await application.get_table("account", "db", "iceberg")
    await application.update_table(
        "account",
        "db",
        "iceberg",
        {**table.definition, "Name": "renamed"},
        version_id=table.version_id,
        skip_archive=False,
    )
    moved = await application.get_table_optimizer("account", "db", "renamed", "compaction")
    assert moved.last_run is not None
    assert moved.last_run.run_id == active_work.run_id
    assert moved.last_run.error == "Owning Glue table was renamed during optimizer execution"
    assert moved.active_run is None
    assert moved.next_run_time == clock.value

    await application.delete_table("account", "db", "renamed")
    with pytest.raises(EntityNotFoundError):
        await application.get_table_optimizer("account", "db", "renamed", "compaction")
