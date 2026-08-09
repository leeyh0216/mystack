"""Private SQLite DB-API connection factory for the Glue catalog adapter.

Every connection receives the configured safety pragmas because SQLite foreign-key enforcement is
connection-local.  Runtime provenance is verified by ``SQLiteRuntimeVerifier`` before the app
lifespan calls catalog initialization.

References:
- https://www.sqlite.org/foreignkeys.html
- https://www.sqlite.org/pragma.html#pragma_busy_timeout
- https://www.sqlite.org/wal.html
"""

from __future__ import annotations

from typing import Any

from mystack.glue.adapters.outbound.sqlite_runtime import (
    ImportingSQLiteDriverLoader,
    SQLiteDriverLoader,
)
from mystack.glue.application.sqlite_runtime import SQLiteRuntimeSettings


class SqliteCatalogConnectionFactory:
    """Create short-lived, fully configured DB-API connections for one catalog file."""

    def __init__(
        self,
        settings: SQLiteRuntimeSettings,
        *,
        driver_loader: SQLiteDriverLoader | None = None,
    ) -> None:
        self._settings = settings
        self._driver_loader = driver_loader or ImportingSQLiteDriverLoader()

    @property
    def settings(self) -> SQLiteRuntimeSettings:
        return self._settings

    def connect(self) -> Any:
        """Open one connection after applying the configured SQLite safety policy."""
        self._settings.database_file.parent.mkdir(parents=True, exist_ok=True)
        driver = self._driver_loader.load(self._settings.driver.module)
        connection = driver.connect(
            str(self._settings.database_file),
            timeout=self._settings.busy_timeout_milliseconds / 1000,
        )
        try:
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self._settings.busy_timeout_milliseconds}")
            connection.execute(f"PRAGMA synchronous = {self._settings.synchronous.upper()}")
            journal = connection.execute(
                f"PRAGMA journal_mode = {self._settings.requested_sqlite_journal_mode.upper()}"
            ).fetchone()
            if (
                journal is None
                or str(journal[0]).lower() != self._settings.requested_sqlite_journal_mode
            ):
                raise RuntimeError("SQLite did not retain the configured journal mode")
            if self._settings.journal_mode == "wal":
                connection.execute(
                    f"PRAGMA wal_autocheckpoint = {self._settings.checkpoint.auto_checkpoint_pages}"
                )
            return connection
        except BaseException:
            connection.close()
            raise
