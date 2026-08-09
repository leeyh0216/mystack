"""Typed SQLite runtime policy owned by the Glue application boundary.

The outbound SQLite adapter consumes these values without exposing SQLite implementation details to
catalog use cases. SQLite WAL requirements are documented at:
https://www.sqlite.org/wal.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_MODULE_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){2,3}")
_JOURNAL_MODES = frozenset({"wal", "rollback"})
_SYNCHRONOUS_POLICIES = frozenset({"off", "normal", "full", "extra"})
_CHECKPOINT_MODES = frozenset({"passive", "full", "restart", "truncate"})
# SQLite documents WAL-reset corruption through 3.51.2 and the first fixed release as 3.51.3:
# https://www.sqlite.org/wal.html#the_wal_reset_bug
_MINIMUM_SAFE_WAL_VERSION = (3, 51, 3)


def sqlite_version_parts(value: str) -> tuple[int, ...]:
    """Return a strictly parsed SQLite version suitable for numeric comparison."""
    if not _VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"SQLite version must contain three or four numeric components: {value!r}")
    return tuple(int(component) for component in value.split("."))


@dataclass(frozen=True, slots=True)
class SQLiteDriverSettings:
    """One explicitly selected DB-API driver and its verified image provenance."""

    module: str
    expected_version: str
    minimum_wal_version: str
    manifest_file: Path

    def __post_init__(self) -> None:
        if not _MODULE_PATTERN.fullmatch(self.module):
            raise ValueError("Glue SQLite driver module must be a dotted Python module name")
        expected = sqlite_version_parts(self.expected_version)
        minimum = sqlite_version_parts(self.minimum_wal_version)
        if minimum < _MINIMUM_SAFE_WAL_VERSION:
            raise ValueError("Glue SQLite minimum_wal_version cannot be below 3.51.3")
        if expected < minimum:
            raise ValueError(
                "Glue SQLite driver expected_version must be at least minimum_wal_version"
            )
        if not str(self.manifest_file):
            raise ValueError("Glue SQLite driver manifest_file cannot be empty")


@dataclass(frozen=True, slots=True)
class SQLiteCheckpointSettings:
    """Explicit WAL checkpoint policy for the SQLite catalog adapter."""

    mode: str
    auto_checkpoint_pages: int

    def __post_init__(self) -> None:
        normalized_mode = self.mode.lower()
        if normalized_mode not in _CHECKPOINT_MODES:
            allowed = ", ".join(sorted(_CHECKPOINT_MODES))
            raise ValueError(f"Glue SQLite checkpoint mode must be one of: {allowed}")
        if self.auto_checkpoint_pages < 0:
            raise ValueError("Glue SQLite auto_checkpoint_pages cannot be negative")
        object.__setattr__(self, "mode", normalized_mode)


@dataclass(frozen=True, slots=True)
class SQLiteRuntimeSettings:
    """File-driven SQLite connection policy with no implicit journal fallback."""

    database_file: Path
    driver: SQLiteDriverSettings
    journal_mode: str
    synchronous: str
    busy_timeout_milliseconds: int
    retry_limit: int
    checkpoint: SQLiteCheckpointSettings

    def __post_init__(self) -> None:
        normalized_journal_mode = self.journal_mode.lower()
        if normalized_journal_mode not in _JOURNAL_MODES:
            allowed = ", ".join(sorted(_JOURNAL_MODES))
            raise ValueError(f"Glue SQLite journal_mode must be one of: {allowed}")
        normalized_synchronous = self.synchronous.lower()
        if normalized_synchronous not in _SYNCHRONOUS_POLICIES:
            allowed = ", ".join(sorted(_SYNCHRONOUS_POLICIES))
            raise ValueError(f"Glue SQLite synchronous must be one of: {allowed}")
        if self.busy_timeout_milliseconds <= 0:
            raise ValueError("Glue SQLite busy_timeout_milliseconds must be positive")
        if self.retry_limit < 0:
            raise ValueError("Glue SQLite retry_limit cannot be negative")
        if not self.database_file.name:
            raise ValueError("Glue SQLite database_file cannot be empty")
        object.__setattr__(self, "journal_mode", normalized_journal_mode)
        object.__setattr__(self, "synchronous", normalized_synchronous)

    @property
    def requested_sqlite_journal_mode(self) -> str:
        """Map the safe user-facing rollback choice to SQLite's DELETE journal mode."""
        return "wal" if self.journal_mode == "wal" else "delete"
