"""Focused Iceberg GlueCatalog commit and inter-process contention contracts.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking
- https://iceberg.apache.org/docs/1.7.1/reliability/#concurrent-write-operations
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import multiprocessing
import os
from pathlib import Path
from queue import Empty
from typing import Any

import pytest
from mystack.aws_protocol import ConfigurationError, load_configuration
from mystack.glue.adapters.outbound import JsonCatalogRepository
from mystack.glue.application import CatalogApplication, CatalogPolicy
from mystack.glue.application.partition_expression import PartitionExpressionPolicy
from mystack.glue.config import GlueSettings
from mystack.glue.domain import VersionMismatchError


class IncrementingClock:
    def __init__(self) -> None:
        self._value = 0.0

    def now(self) -> float:
        self._value += 1.0
        return self._value


def _application(state_file: Path, lock_file: Path) -> CatalogApplication:
    return CatalogApplication(
        JsonCatalogRepository(
            state_file,
            lock_file=lock_file,
            lock_timeout_seconds=_test_timeout(),
            lock_poll_interval_seconds=0.01,
        ),
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


async def _seed(state_file: Path, lock_file: Path) -> None:
    application = _application(state_file, lock_file)
    await application.create_database("account", {"Name": "analytics"})
    await application.create_table(
        "account",
        "analytics",
        _definition("seed", "v0"),
    )


def _commit_worker(
    state_file: str,
    lock_file: str,
    writer: str,
    start: Any,
    ready: Any,
    results: Any,
) -> None:
    async def commit() -> None:
        application = _application(Path(state_file), Path(lock_file))
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
    state_file = tmp_path / "catalog.json"
    lock_file = tmp_path / "catalog.lock"
    await _seed(state_file, lock_file)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    results = context.Queue()
    processes = [
        context.Process(
            target=_commit_worker,
            args=(str(state_file), str(lock_file), writer, start, ready, results),
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
    application = _application(state_file, lock_file)
    table = await application.get_table("account", "analytics", "events")
    document = json.loads(state_file.read_text(encoding="utf-8"))
    assert table.version_id == "1"
    assert table.definition["Parameters"] == _definition(winner, f"v1-{winner}")["Parameters"]
    assert [version.version_id for version in table.archived_versions] == ["0"]
    assert document["state_revision"] == 3
    assert len(document["tables"]) == 1


async def test_archive_policy_and_stale_failure_preserve_committed_metadata(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_file = tmp_path / "catalog.json"
    lock_file = tmp_path / "catalog.lock"
    await _seed(state_file, lock_file)
    application = _application(state_file, lock_file)

    with caplog.at_level(
        logging.INFO,
        logger="mystack.glue.application.iceberg_commit",
    ):
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
    assert table.definition["Parameters"] == _definition("two", "v2")["Parameters"]
    assert [version.version_id for version in table.archived_versions] == ["0"]
    assert all(
        version.definition["Parameters"]["writer"] != "stale" for version in table.versions()
    )
    commit_records = [
        record
        for record in caplog.records
        if record.name == "mystack.glue.application.iceberg_commit"
    ]
    assert {
        "glue.iceberg.commit.begin",
        "glue.iceberg.commit.version.accepted",
        "glue.iceberg.commit.persist.before",
        "glue.iceberg.commit.conflict",
        "glue.iceberg.commit.succeeded",
    } <= {record.getMessage() for record in commit_records}
    assert "s3://" not in repr([getattr(record, "mystack_fields", {}) for record in commit_records])


async def test_catalog_file_lock_wait_is_bounded(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    lock_file = tmp_path / "catalog.lock"
    await _seed(state_file, lock_file)
    descriptor = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        repository = JsonCatalogRepository(
            state_file,
            lock_file=lock_file,
            lock_timeout_seconds=0.05,
            lock_poll_interval_seconds=0.01,
        )
        with pytest.raises(TimeoutError, match="Timed out acquiring catalog lock"):
            await repository.snapshot()
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


async def test_cancelled_lock_wait_releases_late_acquisition(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    lock_file = tmp_path / "catalog.lock"
    await _seed(state_file, lock_file)
    descriptor = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    repository = JsonCatalogRepository(
        state_file,
        lock_file=lock_file,
        lock_timeout_seconds=_test_timeout(),
        lock_poll_interval_seconds=0.01,
    )
    waiting = asyncio.create_task(repository.snapshot())
    try:
        await asyncio.sleep(0.03)
        assert not waiting.done()
        waiting.cancel()
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(waiting, timeout=_test_timeout())
    snapshot = await asyncio.wait_for(repository.snapshot(), timeout=_test_timeout())
    assert ("account", "analytics", "events") in snapshot.tables


def test_catalog_lock_configuration_resolves_paths_and_rejects_invalid_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = GlueSettings.from_configuration(load_configuration("config/mystack.yaml"))
    assert settings.catalog_lock.lock_file == Path("/var/lib/mystack/glue/catalog-state.lock")
    assert settings.catalog_lock.acquire_timeout_seconds == 30.0

    monkeypatch.setenv("MYSTACK__GLUE__CATALOG_LOCK__ACQUIRE_TIMEOUT_SECONDS", "0.01")
    loaded = load_configuration("config/mystack.yaml")
    with pytest.raises(ConfigurationError, match="poll_interval_seconds"):
        GlueSettings.from_configuration(loaded)

    monkeypatch.setenv("MYSTACK__GLUE__CATALOG_LOCK__ACQUIRE_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("MYSTACK__GLUE__CATALOG_LOCK__FILE", "catalog-state.json")
    loaded = load_configuration("config/mystack.yaml")
    with pytest.raises(ConfigurationError, match="must differ"):
        GlueSettings.from_configuration(loaded)


def _test_timeout() -> float:
    return float(os.getenv("MYSTACK_TEST_TIMEOUT_SECONDS", "10"))
