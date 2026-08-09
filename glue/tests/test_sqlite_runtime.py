"""Focused contracts for the source-built Glue SQLite runtime boundary.

References:
- https://www.sqlite.org/wal.html#the_wal_reset_bug
- https://www.sqlite.org/pragma.html#pragma_busy_timeout
"""

from __future__ import annotations

import copy
import json
import logging
import platform
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mystack.aws_protocol import LoadedConfiguration, load_configuration
from mystack.glue.adapters.outbound.sqlite_runtime import (
    SQLiteRuntimeCapabilityError,
    SQLiteRuntimeVerifier,
)
from mystack.glue.app import create_app
from mystack.glue.application.sqlite_runtime import (
    SQLiteCheckpointSettings,
    SQLiteDriverSettings,
    SQLiteRuntimeSettings,
)
from mystack.glue.config import GlueSettings


def _pinned_runtime() -> dict[str, object]:
    return json.loads(Path("config/sqlite-runtime.json").read_text(encoding="utf-8"))


def _pinned_sqlite_version() -> str:
    return str(_pinned_runtime()["sqlite"]["version"])


def _pinned_minimum_wal_version() -> str:
    return str(_pinned_runtime()["sqlite"]["minimum_wal_version"])


def _settings(
    directory: Path,
    *,
    journal_mode: str = "rollback",
    module: str = "sqlite3",
) -> SQLiteRuntimeSettings:
    return SQLiteRuntimeSettings(
        database_file=directory / "catalog.sqlite3",
        driver=SQLiteDriverSettings(
            module=module,
            expected_version=_pinned_sqlite_version(),
            minimum_wal_version=_pinned_minimum_wal_version(),
            manifest_file=directory / "runtime-manifest.json",
        ),
        journal_mode=journal_mode,
        synchronous="full",
        busy_timeout_milliseconds=250,
        retry_limit=3,
        checkpoint=SQLiteCheckpointSettings(mode="passive", auto_checkpoint_pages=1000),
    )


def test_default_runtime_policy_is_file_driven_for_the_sqlite_catalog() -> None:
    settings = GlueSettings.from_configuration(load_configuration("config/mystack.yaml"))
    pins = _pinned_runtime()
    sqlite_pins = pins["sqlite"]

    assert settings.sqlite.database_file == Path("/var/lib/mystack/glue/catalog.sqlite3")
    assert settings.sqlite.driver.module == "pysqlite3.dbapi2"
    assert settings.sqlite.driver.expected_version == sqlite_pins["version"]
    assert settings.sqlite.driver.minimum_wal_version == sqlite_pins["minimum_wal_version"]
    assert settings.sqlite.journal_mode == "wal"
    assert settings.sqlite.retry_limit == 3
    assert settings.sqlite.checkpoint.mode == "passive"


def test_explicit_rollback_driver_is_checked_without_creating_the_catalog_file(
    tmp_path: Path,
) -> None:
    verification = SQLiteRuntimeVerifier(_settings(tmp_path)).verify()

    assert verification.sqlite_version == sqlite3.sqlite_version
    assert verification.journal_mode == "rollback"
    assert verification.manifest_verified is False
    assert verification.foreign_keys_enabled is True
    assert not (tmp_path / "catalog.sqlite3").exists()
    assert list(tmp_path.glob(".mystack-sqlite-probe-*")) == []


def test_health_exposes_the_runtime_verified_before_catalog_initialization(tmp_path: Path) -> None:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path)
    document["glue"]["sqlite"]["journal_mode"] = "rollback"
    document["glue"]["sqlite"]["driver"]["module"] = "sqlite3"
    document["glue"]["table_optimizers"]["enabled"] = False
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"test-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )

    with TestClient(create_app(configuration=configured)) as client:
        health = client.get("/_mystack/health")

    assert health.status_code == 200
    runtime = health.json()["sqlite_runtime"]
    assert runtime["journal_mode"] == "rollback"
    assert runtime["manifest_verified"] is False
    assert runtime["foreign_keys_enabled"] is True
    database_file = tmp_path / "catalog.sqlite3"
    assert database_file.is_file()
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("SELECT schema_version FROM catalog_metadata").fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@dataclass
class UnsafeWALDriver:
    sqlite_version: str = "3.51.2"
    connect_called: bool = False

    def connect(self, database: str, *, timeout: float):
        del database, timeout
        self.connect_called = True
        raise AssertionError("Unsafe WAL versions must fail before a database connection is opened")


class StaticDriverLoader:
    def __init__(self, driver: object) -> None:
        self._driver = driver

    def load(self, module_name: str) -> object:
        assert module_name == "pysqlite3.dbapi2"
        return self._driver


def test_unsafe_wal_driver_fails_closed_before_probe_side_effect(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    driver = UnsafeWALDriver()
    settings = _settings(tmp_path, journal_mode="wal", module="pysqlite3.dbapi2")

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(
            SQLiteRuntimeCapabilityError,
            match="at or above 3.51.3",
        ),
    ):
        SQLiteRuntimeVerifier(settings, driver_loader=StaticDriverLoader(driver)).verify()

    assert driver.connect_called is False
    assert not list(tmp_path.iterdir())
    failure = next(
        record
        for record in caplog.records
        if record.getMessage() == "glue.sqlite.runtime.verify.failed"
    )
    assert failure.mystack_fields["requested_journal_mode"] == "wal"
    assert failure.mystack_fields["fix_hint"]


@dataclass
class JournalFallbackCursor:
    value: object

    def fetchone(self) -> tuple[object, ...]:
        return (self.value,)


class JournalFallbackConnection:
    def close(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def execute(self, sql: str) -> JournalFallbackCursor:
        if sql.startswith("PRAGMA foreign_keys"):
            return JournalFallbackCursor(1)
        if sql.startswith("PRAGMA busy_timeout"):
            return JournalFallbackCursor(250)
        if sql.startswith("PRAGMA synchronous"):
            return JournalFallbackCursor(2)
        if sql.startswith("PRAGMA journal_mode"):
            return JournalFallbackCursor("delete")
        raise AssertionError(f"Unexpected SQLite probe statement: {sql}")


@dataclass
class JournalFallbackDriver:
    sqlite_version: str

    def connect(self, database: str, *, timeout: float) -> JournalFallbackConnection:
        del database, timeout
        return JournalFallbackConnection()


def _write_matching_wal_manifest(settings: SQLiteRuntimeSettings) -> None:
    pins = _pinned_runtime()
    sqlite_pins = pins["sqlite"]
    driver_pins = pins["driver"]
    assert isinstance(sqlite_pins, dict)
    assert isinstance(driver_pins, dict)
    amalgamation = sqlite_pins["amalgamation"]
    source = driver_pins["source"]
    assert isinstance(amalgamation, dict)
    assert isinstance(source, dict)
    settings.driver.manifest_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "architecture": platform.machine(),
                "sqlite": {
                    "version": settings.driver.expected_version,
                    "minimum_wal_version": settings.driver.minimum_wal_version,
                    "amalgamation_sha3_256": amalgamation["sha3_256"],
                },
                "driver": {
                    "distribution": driver_pins["distribution"],
                    "module": settings.driver.module,
                    "version": driver_pins["version"],
                    "source_sha256": source["sha256"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_wal_request_rejects_a_driver_that_reports_rollback_without_downgrade(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, journal_mode="wal", module="pysqlite3.dbapi2")
    _write_matching_wal_manifest(settings)

    with pytest.raises(
        SQLiteRuntimeCapabilityError, match="did not activate the requested journal"
    ):
        SQLiteRuntimeVerifier(
            settings,
            driver_loader=StaticDriverLoader(JournalFallbackDriver(_pinned_sqlite_version())),
        ).verify()

    assert not (tmp_path / "catalog.sqlite3").exists()
    assert list(tmp_path.glob(".mystack-sqlite-probe-*")) == []


class FailingVerifier:
    def verify(self):
        raise SQLiteRuntimeCapabilityError("runtime preflight rejected WAL")


class GuardedCatalogApplication:
    def __init__(self) -> None:
        self.initialized = False

    async def initialize(self) -> None:
        self.initialized = True


def test_runtime_preflight_stops_catalog_initialization_before_side_effect(tmp_path: Path) -> None:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path / "uncreated-data-root")
    document["glue"]["table_optimizers"]["work_root"] = "must-not-exist-before-preflight"
    document["glue"]["table_optimizers"]["enabled"] = False
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"test-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )
    application = GuardedCatalogApplication()

    with pytest.raises(SQLiteRuntimeCapabilityError, match="preflight rejected"):
        with TestClient(
            create_app(
                configuration=configured,
                application=application,  # type: ignore[arg-type]
                sqlite_runtime_verifier=FailingVerifier(),  # type: ignore[arg-type]
            )
        ):
            pass

    assert application.initialized is False
    assert not (tmp_path / "uncreated-data-root").exists()
    assert not (tmp_path / "must-not-exist-before-preflight").exists()
