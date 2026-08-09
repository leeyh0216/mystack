"""Verified private SQLite DB-API runtime for the Glue catalog adapter.

The implementation keeps SQLite behind an outbound adapter. WAL is enabled only after the driver
version, source-build manifest, PRAGMAs, and writable sibling-file directory have been verified.

References:
- https://www.sqlite.org/wal.html#the_wal_reset_bug
- https://www.sqlite.org/pragma.html#pragma_journal_mode
- https://www.sqlite.org/pragma.html#pragma_busy_timeout
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import platform
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast

from mystack.aws_protocol import ConfigurationError
from mystack.aws_protocol.observability import log_event
from mystack.glue.application.sqlite_runtime import (
    SQLiteRuntimeSettings,
    sqlite_version_parts,
)

_LOGGER = logging.getLogger(__name__)
_MANIFEST_FIELDS = frozenset({"schema_version", "architecture", "sqlite", "driver"})
_MANIFEST_SQLITE_FIELDS = frozenset({"version", "minimum_wal_version", "amalgamation_sha3_256"})
_MANIFEST_DRIVER_FIELDS = frozenset({"distribution", "module", "version", "source_sha256"})
_SYNCHRONOUS_VALUES = {"off": 0, "normal": 1, "full": 2, "extra": 3}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class SQLiteRuntimeCapabilityError(ConfigurationError):
    """The configured SQLite runtime cannot safely provide the requested journal mode."""


class SQLiteCursor(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...


class SQLiteConnection(Protocol):
    def close(self) -> None: ...

    def commit(self) -> None: ...

    def execute(self, sql: str) -> SQLiteCursor: ...


class SQLiteDriver(Protocol):
    sqlite_version: str

    def connect(self, database: str, *, timeout: float) -> SQLiteConnection: ...


class SQLiteDriverLoader(Protocol):
    def load(self, module_name: str) -> SQLiteDriver: ...


class ImportingSQLiteDriverLoader:
    """Load only the DB-API module named by mounted configuration."""

    def load(self, module_name: str) -> SQLiteDriver:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name == module_name.split(".", maxsplit=1)[0]:
                raise SQLiteRuntimeCapabilityError(
                    "Configured Glue SQLite driver is unavailable. Build or run the reviewed Glue "
                    "image, or explicitly configure a rollback-journal development driver."
                ) from error
            raise
        return _validated_driver(module, module_name)


@dataclass(frozen=True, slots=True)
class SQLiteRuntimeVerification:
    """Safe runtime facts exposed through health and image-preflight evidence."""

    driver_module: str
    architecture: str
    sqlite_version: str
    manifest_verified: bool
    journal_mode: str
    synchronous: str
    busy_timeout_milliseconds: int
    foreign_keys_enabled: bool
    checkpoint_mode: str
    auto_checkpoint_pages: int

    def document(self) -> dict[str, object]:
        return {
            "driver_module": self.driver_module,
            "architecture": self.architecture,
            "sqlite_version": self.sqlite_version,
            "manifest_verified": self.manifest_verified,
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "busy_timeout_milliseconds": self.busy_timeout_milliseconds,
            "foreign_keys_enabled": self.foreign_keys_enabled,
            "checkpoint_mode": self.checkpoint_mode,
            "auto_checkpoint_pages": self.auto_checkpoint_pages,
        }


class SQLiteRuntimeVerifier:
    """Fail before catalog initialization when the selected SQLite runtime is unsafe."""

    def __init__(
        self,
        settings: SQLiteRuntimeSettings,
        *,
        driver_loader: SQLiteDriverLoader | None = None,
    ) -> None:
        self._settings = settings
        self._driver_loader = driver_loader or ImportingSQLiteDriverLoader()

    def verify(self) -> SQLiteRuntimeVerification:
        """Open and remove an isolated probe database after every configured capability succeeds."""
        settings = self._settings
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.sqlite.runtime.verify.before",
            database_directory=str(settings.database_file.parent),
            driver_module=settings.driver.module,
            requested_journal_mode=settings.journal_mode,
            synchronous=settings.synchronous,
            busy_timeout_milliseconds=settings.busy_timeout_milliseconds,
            retry_limit=settings.retry_limit,
            checkpoint_mode=settings.checkpoint.mode,
            auto_checkpoint_pages=settings.checkpoint.auto_checkpoint_pages,
        )
        probe_path: Path | None = None
        connection: SQLiteConnection | None = None
        try:
            driver = self._driver_loader.load(settings.driver.module)
            sqlite_version = _driver_version(driver)
            manifest_verified = self._verify_driver_provenance(sqlite_version)
            probe_path = self._create_probe_path()
            connection = driver.connect(
                str(probe_path),
                timeout=settings.busy_timeout_milliseconds / 1000,
            )
            foreign_keys_enabled = self._configure_connection(connection, probe_path)
            verification = SQLiteRuntimeVerification(
                driver_module=settings.driver.module,
                architecture=platform.machine(),
                sqlite_version=sqlite_version,
                manifest_verified=manifest_verified,
                journal_mode=settings.journal_mode,
                synchronous=settings.synchronous,
                busy_timeout_milliseconds=settings.busy_timeout_milliseconds,
                foreign_keys_enabled=foreign_keys_enabled,
                checkpoint_mode=settings.checkpoint.mode,
                auto_checkpoint_pages=settings.checkpoint.auto_checkpoint_pages,
            )
        except SQLiteRuntimeCapabilityError as error:
            self._log_failure(error)
            raise
        except Exception as error:
            self._log_failure(error)
            raise SQLiteRuntimeCapabilityError(
                "Glue SQLite runtime capability check failed before catalog initialization. "
                "Inspect glue.sqlite configuration and the structured glue.sqlite.runtime events."
            ) from error
        finally:
            close_error: Exception | None = None
            if connection is not None:
                try:
                    connection.close()
                except Exception as error:
                    close_error = error
                    log_event(
                        _LOGGER,
                        logging.WARNING,
                        "glue.sqlite.runtime.probe_close.failed",
                        driver_module=settings.driver.module,
                        fix_hint="inspect the selected DB-API driver close behavior",
                        exc_info=True,
                    )
            if probe_path is not None:
                _remove_probe_files(probe_path)
            if close_error is not None and sys.exc_info()[0] is None:
                raise SQLiteRuntimeCapabilityError(
                    "Configured SQLite driver could not close its capability probe safely."
                ) from close_error

        log_event(
            _LOGGER,
            logging.INFO,
            "glue.sqlite.runtime.verify.after",
            **verification.document(),
        )
        return verification

    def _verify_driver_provenance(self, sqlite_version: str) -> bool:
        settings = self._settings
        if settings.journal_mode != "wal":
            return False
        actual = sqlite_version_parts(sqlite_version)
        minimum = sqlite_version_parts(settings.driver.minimum_wal_version)
        if actual < minimum:
            raise SQLiteRuntimeCapabilityError(
                "Configured WAL requires a SQLite version at or above "
                f"{settings.driver.minimum_wal_version}; loaded {sqlite_version}. "
                "Mystack will not downgrade WAL to rollback automatically."
            )
        if sqlite_version != settings.driver.expected_version:
            raise SQLiteRuntimeCapabilityError(
                "Configured WAL driver version does not match the reviewed source build: "
                f"expected {settings.driver.expected_version}, loaded {sqlite_version}."
            )
        manifest = _load_manifest(settings.driver.manifest_file)
        _validate_manifest(manifest, settings, sqlite_version)
        return True

    def _create_probe_path(self) -> Path:
        directory = self._settings.database_file.parent
        directory.mkdir(parents=True, exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".mystack-sqlite-probe-",
            suffix=".db",
            dir=directory,
        )
        os.close(descriptor)
        path = Path(raw_path)
        path.unlink()
        return path

    def _configure_connection(self, connection: SQLiteConnection, probe_path: Path) -> bool:
        settings = self._settings
        _execute(connection, "PRAGMA foreign_keys = ON")
        foreign_keys = _int_pragma(connection, "PRAGMA foreign_keys")
        if foreign_keys != 1:
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite driver cannot enable foreign-key enforcement."
            )

        _execute(connection, f"PRAGMA busy_timeout = {settings.busy_timeout_milliseconds}")
        busy_timeout = _int_pragma(connection, "PRAGMA busy_timeout")
        if busy_timeout != settings.busy_timeout_milliseconds:
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite driver did not retain the requested busy_timeout."
            )

        _execute(connection, f"PRAGMA synchronous = {settings.synchronous.upper()}")
        synchronous = _int_pragma(connection, "PRAGMA synchronous")
        if synchronous != _SYNCHRONOUS_VALUES[settings.synchronous]:
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite driver did not retain the requested synchronous policy."
            )

        expected_journal_mode = settings.requested_sqlite_journal_mode
        journal_mode = _text_pragma(
            connection,
            f"PRAGMA journal_mode = {expected_journal_mode.upper()}",
        )
        if journal_mode != expected_journal_mode:
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite driver did not activate the requested journal mode. "
                "Mystack will not substitute a different journal mode."
            )

        if settings.journal_mode == "wal":
            _execute(
                connection,
                f"PRAGMA wal_autocheckpoint = {settings.checkpoint.auto_checkpoint_pages}",
            )
            auto_checkpoint_pages = _int_pragma(connection, "PRAGMA wal_autocheckpoint")
            if auto_checkpoint_pages != settings.checkpoint.auto_checkpoint_pages:
                raise SQLiteRuntimeCapabilityError(
                    "Configured SQLite driver did not retain the requested WAL "
                    "auto-checkpoint policy."
                )
            _execute(connection, "CREATE TABLE __mystack_runtime_probe (id INTEGER PRIMARY KEY)")
            _execute(connection, "INSERT INTO __mystack_runtime_probe (id) VALUES (1)")
            connection.commit()
            self._verify_wal_siblings(probe_path)
            checkpoint = _execute(
                connection,
                f"PRAGMA wal_checkpoint({settings.checkpoint.mode.upper()})",
            ).fetchone()
            if checkpoint is None or int(checkpoint[0]) != 0:
                raise SQLiteRuntimeCapabilityError(
                    "Configured SQLite driver could not complete the requested WAL "
                    "checkpoint probe."
                )
        return True

    def _verify_wal_siblings(self, probe_path: Path) -> None:
        wal_path = probe_path.with_name(probe_path.name + "-wal")
        if not wal_path.is_file():
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite directory cannot create the required WAL sibling file."
            )
        shm_path = wal_path.with_name(wal_path.name.removesuffix("-wal") + "-shm")
        if not shm_path.is_file():
            raise SQLiteRuntimeCapabilityError(
                "Configured SQLite directory cannot create the required WAL shared-memory file."
            )

    def _log_failure(self, error: Exception) -> None:
        log_event(
            _LOGGER,
            logging.ERROR,
            "glue.sqlite.runtime.verify.failed",
            driver_module=self._settings.driver.module,
            requested_journal_mode=self._settings.journal_mode,
            failure_type=type(error).__name__,
            fix_hint=(
                "inspect glue.sqlite.driver, journal_mode, database_file volume, and the image "
                "runtime manifest"
            ),
            exc_info=True,
        )


def _validated_driver(module: ModuleType, module_name: str) -> SQLiteDriver:
    connect = getattr(module, "connect", None)
    sqlite_version = getattr(module, "sqlite_version", None)
    if not callable(connect) or not isinstance(sqlite_version, str):
        raise SQLiteRuntimeCapabilityError(
            f"Configured Glue SQLite driver {module_name!r} does not expose the "
            "required DB-API surface."
        )
    return cast(SQLiteDriver, module)


def _driver_version(driver: SQLiteDriver) -> str:
    value = driver.sqlite_version
    try:
        sqlite_version_parts(value)
    except ValueError as error:
        raise SQLiteRuntimeCapabilityError(
            "Configured Glue SQLite driver reported an invalid SQLite version."
        ) from error
    return value


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver build manifest is unavailable or invalid."
        ) from error
    if not isinstance(document, dict):
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver build manifest must be a JSON object."
        )
    return cast(dict[str, object], document)


def _validate_manifest(
    manifest: dict[str, object],
    settings: SQLiteRuntimeSettings,
    sqlite_version: str,
) -> None:
    if set(manifest) != _MANIFEST_FIELDS or manifest.get("schema_version") != 1:
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver build manifest has an unsupported shape."
        )
    sqlite = manifest.get("sqlite")
    driver = manifest.get("driver")
    if not isinstance(sqlite, dict) or set(sqlite) != _MANIFEST_SQLITE_FIELDS:
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver manifest has invalid SQLite provenance."
        )
    if not isinstance(driver, dict) or set(driver) != _MANIFEST_DRIVER_FIELDS:
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver manifest has invalid driver provenance."
        )
    if (
        not isinstance(manifest.get("architecture"), str)
        or manifest["architecture"] != platform.machine()
        or not isinstance(sqlite.get("amalgamation_sha3_256"), str)
        or not _SHA256_PATTERN.fullmatch(sqlite["amalgamation_sha3_256"])
        or not isinstance(driver.get("distribution"), str)
        or not isinstance(driver.get("version"), str)
        or not isinstance(driver.get("source_sha256"), str)
        or not _SHA256_PATTERN.fullmatch(driver["source_sha256"])
    ):
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver manifest has invalid architecture or source-digest provenance."
        )
    if (
        sqlite.get("version") != sqlite_version
        or sqlite.get("minimum_wal_version") != settings.driver.minimum_wal_version
        or driver.get("module") != settings.driver.module
    ):
        raise SQLiteRuntimeCapabilityError(
            "Configured WAL driver manifest does not match the mounted SQLite runtime policy."
        )


def _execute(connection: SQLiteConnection, sql: str) -> SQLiteCursor:
    return connection.execute(sql)


def _int_pragma(connection: SQLiteConnection, sql: str) -> int:
    value = _one_value(connection, sql)
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise SQLiteRuntimeCapabilityError(
            f"SQLite pragma did not return an integer: {sql}"
        ) from error


def _text_pragma(connection: SQLiteConnection, sql: str) -> str:
    value = _one_value(connection, sql)
    if not isinstance(value, str):
        raise SQLiteRuntimeCapabilityError(f"SQLite pragma did not return text: {sql}")
    return value.lower()


def _one_value(connection: SQLiteConnection, sql: str) -> object:
    row = _execute(connection, sql).fetchone()
    if row is None or not row:
        raise SQLiteRuntimeCapabilityError(f"SQLite pragma returned no value: {sql}")
    return row[0]


def _remove_probe_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            path.with_name(path.name + suffix).unlink(missing_ok=True)
        except OSError:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.sqlite.runtime.probe_cleanup.failed",
                probe_directory=str(path.parent),
                fix_hint=(
                    "remove only .mystack-sqlite-probe-* files after no SQLite process uses them"
                ),
            )
