"""Transactional and durable Data Catalog adapter contracts.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://docs.aws.amazon.com/glue/latest/dg/tables-described.html
- https://docs.python.org/3/library/os.html#os.replace
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest
from mystack.glue.adapters.outbound import (
    CatalogStateStore,
    JsonCatalogRepository,
    TransactionalCatalogRepository,
)
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.domain import (
    CatalogState,
    EntityNotFoundError,
    TableOptimizer,
    TableOptimizerConfiguration,
    TableOptimizerType,
    VersionMismatchError,
)

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


class ToggleFailureStore(CatalogStateStore):
    def __init__(self) -> None:
        self.committed = CatalogState()
        self.fail = False

    def load(self) -> CatalogState:
        return copy.deepcopy(self.committed)

    async def save(self, candidate: CatalogState) -> None:
        if self.fail:
            raise OSError("injected persistence failure")
        self.committed = copy.deepcopy(candidate)


class BlockingStore(ToggleFailureStore):
    def __init__(self) -> None:
        super().__init__()
        self.block = False
        self.save_started = asyncio.Event()
        self.allow_save = asyncio.Event()

    async def save(self, candidate: CatalogState) -> None:
        if self.block:
            self.save_started.set()
            await self.allow_save.wait()
        await super().save(candidate)


def _application(repository) -> CatalogApplication:
    return CatalogApplication(
        repository,
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


async def test_catalog_state_survives_repository_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    await _catalog_tree(_application(JsonCatalogRepository(state_file)))

    restarted = _application(JsonCatalogRepository(state_file))

    assert (await restarted.get_database("account", "db")).definition == {"Name": "db"}
    assert (await restarted.get_table("account", "db", "table")).version_id == "0"
    partition = await restarted.get_partition(
        "account",
        "db",
        "table",
        ("2026-08-08",),
    )
    assert partition.values == ("2026-08-08",)


async def test_persistence_failure_keeps_visible_and_durable_state_unchanged() -> None:
    store = ToggleFailureStore()
    repository = TransactionalCatalogRepository(store)
    application = _application(repository)
    await _catalog_tree(application)
    committed_before = copy.deepcopy(store.committed)
    store.fail = True

    with pytest.raises(OSError, match="injected persistence failure"):
        await application.update_database("account", "db", {"Name": "renamed"})

    assert await application.get_database("account", "db")
    with pytest.raises(EntityNotFoundError):
        await application.get_database("account", "renamed")
    assert store.committed == committed_before


async def test_table_rename_persistence_failure_rolls_back_table_and_partitions() -> None:
    """The UpdateTable candidate is invisible unless its durable save succeeds.

    Reference: https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
    """
    store = ToggleFailureStore()
    application = _application(TransactionalCatalogRepository(store))
    await _catalog_tree(application)
    committed_before = copy.deepcopy(store.committed)
    store.fail = True

    with pytest.raises(OSError, match="injected persistence failure"):
        await application.update_table(
            "account",
            "db",
            "table",
            {
                "Name": "renamed",
                "PartitionKeys": [{"Name": "day", "Type": "string"}],
            },
            version_id="0",
            skip_archive=False,
        )

    assert (await application.get_table("account", "db", "table")).version_id == "0"
    assert (
        await application.get_partition(
            "account",
            "db",
            "table",
            ("2026-08-08",),
        )
    ).table_name == "table"
    with pytest.raises(EntityNotFoundError):
        await application.get_table("account", "db", "renamed")
    assert store.committed == committed_before


async def test_atomic_replace_failure_preserves_file_and_visible_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = tmp_path / "catalog.json"
    repository = JsonCatalogRepository(state_file)
    application = _application(repository)
    await _catalog_tree(application)
    committed_before = state_file.read_bytes()

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("injected atomic replace failure")

    monkeypatch.setattr(
        "mystack.glue.adapters.outbound.repository.os.replace",
        fail_replace,
    )
    with pytest.raises(OSError, match="injected atomic replace failure"):
        await application.update_database("account", "db", {"Name": "renamed"})

    assert state_file.read_bytes() == committed_before
    assert await application.get_database("account", "db")
    with pytest.raises(EntityNotFoundError):
        await application.get_database("account", "renamed")


async def test_database_and_table_renames_commit_children_atomically(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    application = _application(JsonCatalogRepository(state_file))
    await _catalog_tree(application)

    await application.update_database("account", "db", {"Name": "warehouse"})
    await application.update_table(
        "account",
        "warehouse",
        "table",
        {"Name": "events", "PartitionKeys": [{"Name": "day", "Type": "string"}]},
        version_id="0",
        skip_archive=False,
    )

    restarted = _application(JsonCatalogRepository(state_file))
    table = await restarted.get_table("account", "warehouse", "events")
    partition = await restarted.get_partition(
        "account",
        "warehouse",
        "events",
        ("2026-08-08",),
    )
    assert table.version_id == "1"
    assert partition.database_name == "warehouse"
    assert partition.table_name == "events"
    with pytest.raises(EntityNotFoundError):
        await restarted.get_database("account", "db")


async def test_concurrent_updates_increment_authoritative_version_without_loss() -> None:
    application = _application(TransactionalCatalogRepository(ToggleFailureStore()))
    await _catalog_tree(application)

    await asyncio.gather(
        application.update_table(
            "account",
            "db",
            "table",
            {"Name": "table", "Parameters": {"writer": "one"}},
            version_id=None,
            skip_archive=False,
        ),
        application.update_table(
            "account",
            "db",
            "table",
            {"Name": "table", "Parameters": {"writer": "two"}},
            version_id=None,
            skip_archive=False,
        ),
    )

    table = await application.get_table("account", "db", "table")
    versions, _ = await application.get_table_versions(
        "account",
        "db",
        "table",
        next_token=None,
        max_results=None,
    )
    assert table.version_id == "2"
    assert [version.version_id for version in versions] == ["0", "1", "2"]


async def test_table_version_compare_and_swap_rejects_stale_writer() -> None:
    application = _application(TransactionalCatalogRepository(ToggleFailureStore()))
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
    assert (await application.get_table("account", "db", "table")).version_id == "1"


async def test_cancellation_during_durable_commit_cannot_split_visible_state() -> None:
    store = BlockingStore()
    repository = TransactionalCatalogRepository(store)
    application = _application(repository)
    await _catalog_tree(application)
    store.block = True
    update = asyncio.create_task(application.update_database("account", "db", {"Name": "renamed"}))
    await store.save_started.wait()

    update.cancel()
    store.allow_save.set()
    with pytest.raises(asyncio.CancelledError):
        await update

    assert await application.get_database("account", "renamed")
    assert ("account", "renamed") in store.committed.databases
    assert (await repository.snapshot()) == store.committed


async def test_delete_database_cascades_in_one_durable_commit(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    application = _application(JsonCatalogRepository(state_file))
    await _catalog_tree(application)

    await application.delete_database("account", "db")

    restarted = _application(JsonCatalogRepository(state_file))
    with pytest.raises(EntityNotFoundError):
        await restarted.get_database("account", "db")
    document = json.loads(state_file.read_text(encoding="utf-8"))
    assert document["databases"] == []
    assert document["tables"] == []
    assert document["partitions"] == []


@pytest.mark.parametrize("source_schema", [1, 2])
async def test_legacy_state_is_migrated_to_schema_three_on_next_commit(
    tmp_path: Path,
    source_schema: int,
) -> None:
    state_file = tmp_path / "catalog.json"
    state_file.write_text(
        json.dumps(
            {
                "schema_version": source_schema,
                "state_revision": 0,
                "databases": [
                    {
                        "catalog_id": "account",
                        "name": "legacy",
                        "definition": {"Name": "legacy"},
                        "create_time": 1.0,
                    }
                ],
                "tables": [],
                "partitions": [],
            }
        ),
        encoding="utf-8",
    )
    application = _application(JsonCatalogRepository(state_file))

    await application.create_database("account", {"Name": "new"})

    document = json.loads(state_file.read_text(encoding="utf-8"))
    assert document["schema_version"] == 3
    assert document["state_revision"] == 1
    assert document["optimizers"] == []
    assert {value["name"] for value in document["databases"]} == {"legacy", "new"}


async def test_optimizer_state_and_run_history_survive_repository_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    repository = JsonCatalogRepository(state_file)
    application = _application(repository)
    await application.create_database("account", {"Name": "db"})
    await application.create_table(
        "account",
        "db",
        {
            "Name": "table",
            "Parameters": {"table_type": "ICEBERG", "metadata_location": "s3://b/m/v1.json"},
            "StorageDescriptor": {"Location": "s3://b/t", "InputFormat": "parquet"},
        },
    )
    configuration = TableOptimizerConfiguration.parse(
        TableOptimizerType.COMPACTION,
        {},
        table_location="s3://b/t",
    )
    optimizer = TableOptimizer.create(
        catalog_id="account",
        database_name="db",
        table_name="table",
        optimizer_type=TableOptimizerType.COMPACTION,
        configuration=configuration,
        now=1.0,
        initial_delay_seconds=0.0,
    ).claim("run-1", 1.0, history_limit=10)
    optimizer = optimizer.mark_in_progress("run-1").complete_run(
        "run-1",
        now=2.0,
        metrics={"NumberOfFilesCompacted": "3"},
        compaction_interval_seconds=3600.0,
    )
    async with repository.transaction(
        operation="test-create-optimizer",
        resource_key=optimizer.key,
    ) as state:
        state.optimizers[optimizer.key] = optimizer

    restored = await JsonCatalogRepository(state_file).snapshot()

    assert restored.optimizers[optimizer.key] == optimizer
    assert json.loads(state_file.read_text(encoding="utf-8"))["schema_version"] == 3
