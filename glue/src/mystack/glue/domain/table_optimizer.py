"""Immutable AWS Glue Iceberg table-optimizer state and transitions.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
- https://docs.aws.amazon.com/glue/latest/dg/optimizer-notes.html
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any
from urllib.parse import SplitResult, urlsplit

from mystack.glue.domain.errors import InvalidInputError
from mystack.glue.domain.model import CatalogDocument, CatalogName

TableOptimizerKey = tuple[str, str, str, str]


class TableOptimizerType(StrEnum):
    COMPACTION = "compaction"
    RETENTION = "retention"
    ORPHAN_FILE_DELETION = "orphan_file_deletion"

    @classmethod
    def parse(cls, raw: object) -> TableOptimizerType:
        try:
            return cls(str(raw))
        except ValueError as error:
            raise InvalidInputError(f"Unsupported table optimizer type {raw!r}") from error

    @property
    def configuration_member(self) -> str:
        return {
            TableOptimizerType.COMPACTION: "compactionConfiguration",
            TableOptimizerType.RETENTION: "retentionConfiguration",
            TableOptimizerType.ORPHAN_FILE_DELETION: "orphanFileDeletionConfiguration",
        }[self]


class TableOptimizerEventType(StrEnum):
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TableOptimizerConfigurationDraft:
    """Table-independent, normalized optimizer input awaiting its table location."""

    optimizer_type: TableOptimizerType
    _document: CatalogDocument

    @classmethod
    def parse(
        cls,
        optimizer_type: TableOptimizerType,
        raw: object,
    ) -> TableOptimizerConfigurationDraft:
        if not isinstance(raw, dict):
            raise InvalidInputError("TableOptimizerConfiguration must be an object")
        document = copy.deepcopy(raw)
        _validate_common_configuration(document)
        type_members = {
            "compactionConfiguration",
            "retentionConfiguration",
            "orphanFileDeletionConfiguration",
        }
        mismatched = (set(document) & type_members) - {optimizer_type.configuration_member}
        if mismatched:
            raise InvalidInputError(
                f"Optimizer type {optimizer_type.value!r} cannot use {sorted(mismatched)!r}"
            )
        enabled = document.get("enabled", True)
        if not isinstance(enabled, bool):
            raise InvalidInputError("Table optimizer enabled must be a Boolean")
        document["enabled"] = enabled
        member = optimizer_type.configuration_member
        type_document = _mapping(document.get(member, {}), member)
        iceberg = _mapping(
            type_document.get("icebergConfiguration", {}),
            f"{member}.icebergConfiguration",
        )
        if optimizer_type is TableOptimizerType.COMPACTION:
            normalized_iceberg = _compaction_configuration(iceberg)
        elif optimizer_type is TableOptimizerType.RETENTION:
            normalized_iceberg = _retention_configuration(iceberg)
        else:
            normalized_iceberg = _orphan_configuration_input(iceberg)
        document[member] = {"icebergConfiguration": normalized_iceberg}
        return cls(optimizer_type, CatalogDocument(document))

    def bind(self, *, table_location: str) -> TableOptimizerConfiguration:
        document = self._document.to_dict()
        if self.optimizer_type is TableOptimizerType.ORPHAN_FILE_DELETION:
            member = self.optimizer_type.configuration_member
            iceberg = document[member]["icebergConfiguration"]
            document[member]["icebergConfiguration"] = _bind_orphan_location(
                iceberg,
                table_location=table_location,
            )
        return TableOptimizerConfiguration(self.optimizer_type, CatalogDocument(document))


@dataclass(frozen=True, slots=True)
class TableOptimizerConfiguration:
    """Validated, table-bound configuration with AWS-documented defaults."""

    optimizer_type: TableOptimizerType
    _document: CatalogDocument

    @classmethod
    def parse(
        cls,
        optimizer_type: TableOptimizerType,
        raw: object,
        *,
        table_location: str,
    ) -> TableOptimizerConfiguration:
        return TableOptimizerConfigurationDraft.parse(optimizer_type, raw).bind(
            table_location=table_location
        )

    @classmethod
    def restore(
        cls,
        optimizer_type: str,
        document: dict[str, Any],
    ) -> TableOptimizerConfiguration:
        return cls(TableOptimizerType.parse(optimizer_type), CatalogDocument(document))

    @property
    def document(self) -> dict[str, Any]:
        return self._document.to_dict()

    @property
    def enabled(self) -> bool:
        return bool(self._document.get("enabled", False))

    def run_interval_seconds(self, *, compaction_interval_seconds: float) -> float:
        if self.optimizer_type is TableOptimizerType.COMPACTION:
            return compaction_interval_seconds
        iceberg = self._document.get(self.optimizer_type.configuration_member)[
            "icebergConfiguration"
        ]
        return float(iceberg["runRateInHours"]) * 3600.0

    def disabled(self) -> TableOptimizerConfiguration:
        document = self.document
        document["enabled"] = False
        return TableOptimizerConfiguration(self.optimizer_type, CatalogDocument(document))


@dataclass(frozen=True, slots=True)
class TableOptimizerRun:
    run_id: str
    event_type: TableOptimizerEventType
    start_timestamp: float
    end_timestamp: float | None = None
    _configuration: CatalogDocument | None = None
    _metrics: CatalogDocument | None = None
    error: str | None = None

    @classmethod
    def starting(
        cls,
        run_id: str,
        now: float,
        configuration: dict[str, Any],
    ) -> TableOptimizerRun:
        return cls(
            run_id,
            TableOptimizerEventType.STARTING,
            now,
            _configuration=CatalogDocument(configuration),
        )

    @classmethod
    def restore(
        cls,
        *,
        run_id: str,
        event_type: str,
        start_timestamp: float,
        end_timestamp: float | None,
        configuration: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        error: str | None,
    ) -> TableOptimizerRun:
        return cls(
            run_id,
            TableOptimizerEventType(event_type),
            start_timestamp,
            end_timestamp,
            CatalogDocument(configuration) if configuration is not None else None,
            CatalogDocument(metrics) if metrics is not None else None,
            error,
        )

    @property
    def terminal(self) -> bool:
        return self.event_type in {
            TableOptimizerEventType.COMPLETED,
            TableOptimizerEventType.FAILED,
        }

    @property
    def metrics(self) -> dict[str, Any] | None:
        return None if self._metrics is None else self._metrics.to_dict()

    @property
    def configuration(self) -> dict[str, Any] | None:
        return None if self._configuration is None else self._configuration.to_dict()

    def begin(self) -> TableOptimizerRun:
        if self.event_type is not TableOptimizerEventType.STARTING:
            raise InvalidInputError("Only a starting optimizer run can enter in_progress")
        return replace(self, event_type=TableOptimizerEventType.IN_PROGRESS)

    def complete(self, now: float, metrics: dict[str, Any]) -> TableOptimizerRun:
        if self.event_type not in {
            TableOptimizerEventType.STARTING,
            TableOptimizerEventType.IN_PROGRESS,
        }:
            raise InvalidInputError("Only an active optimizer run can complete")
        return replace(
            self,
            event_type=TableOptimizerEventType.COMPLETED,
            end_timestamp=now,
            _metrics=CatalogDocument(metrics),
            error=None,
        )

    def fail(self, now: float, error: str) -> TableOptimizerRun:
        if self.terminal:
            raise InvalidInputError("A terminal optimizer run cannot fail again")
        return replace(
            self,
            event_type=TableOptimizerEventType.FAILED,
            end_timestamp=now,
            _metrics=None,
            error=str(error),
        )


@dataclass(frozen=True, slots=True)
class TableOptimizer:
    catalog_id: str
    _database_name: CatalogName
    _table_name: CatalogName
    optimizer_type: TableOptimizerType
    configuration: TableOptimizerConfiguration
    create_time: float
    update_time: float
    next_run_time: float | None
    revision: int = 0
    runs: tuple[TableOptimizerRun, ...] = ()
    consecutive_failures: int = 0

    @classmethod
    def create(
        cls,
        *,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: TableOptimizerType,
        configuration: TableOptimizerConfiguration,
        now: float,
        initial_delay_seconds: float,
    ) -> TableOptimizer:
        next_run = now + initial_delay_seconds if configuration.enabled else None
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            CatalogName.parse(table_name),
            optimizer_type,
            configuration,
            now,
            now,
            next_run,
        )

    @classmethod
    def restore(
        cls,
        *,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: str,
        configuration: dict[str, Any],
        create_time: float,
        update_time: float,
        next_run_time: float | None,
        revision: int,
        runs: tuple[TableOptimizerRun, ...],
        consecutive_failures: int,
    ) -> TableOptimizer:
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            CatalogName.parse(table_name),
            TableOptimizerType.parse(optimizer_type),
            TableOptimizerConfiguration.restore(optimizer_type, configuration),
            create_time,
            update_time,
            next_run_time,
            revision,
            runs,
            consecutive_failures,
        )

    @property
    def database_name(self) -> str:
        return self._database_name.value

    @property
    def table_name(self) -> str:
        return self._table_name.value

    @property
    def key(self) -> TableOptimizerKey:
        return (
            self.catalog_id,
            self.database_name,
            self.table_name,
            self.optimizer_type.value,
        )

    @property
    def active_run(self) -> TableOptimizerRun | None:
        if self.runs and not self.runs[-1].terminal:
            return self.runs[-1]
        return None

    @property
    def last_run(self) -> TableOptimizerRun | None:
        return self.runs[-1] if self.runs else None

    def move_database(self, database_name: str) -> TableOptimizer:
        return replace(self, _database_name=CatalogName.parse(database_name))

    def move_table(self, table_name: str) -> TableOptimizer:
        return replace(self, _table_name=CatalogName.parse(table_name))

    def revise(
        self,
        configuration: TableOptimizerConfiguration,
        *,
        now: float,
        initial_delay_seconds: float,
    ) -> TableOptimizer:
        next_run = now + initial_delay_seconds if configuration.enabled else None
        return replace(
            self,
            configuration=configuration,
            update_time=now,
            next_run_time=next_run,
            revision=self.revision + 1,
            consecutive_failures=0,
        )

    def claim(self, run_id: str, now: float, *, history_limit: int) -> TableOptimizer:
        if not self.configuration.enabled:
            raise InvalidInputError("A disabled table optimizer cannot start")
        if self.active_run is not None:
            raise InvalidInputError("A table optimizer run is already active")
        if self.next_run_time is None or self.next_run_time > now:
            raise InvalidInputError("Table optimizer is not due")
        runs = (
            *self.runs,
            TableOptimizerRun.starting(run_id, now, self.configuration.document),
        )[-history_limit:]
        return replace(self, runs=runs, next_run_time=None)

    def mark_in_progress(self, run_id: str) -> TableOptimizer:
        run = self._require_active_run(run_id)
        return replace(self, runs=(*self.runs[:-1], run.begin()))

    def complete_run(
        self,
        run_id: str,
        *,
        now: float,
        metrics: dict[str, Any],
        compaction_interval_seconds: float,
    ) -> TableOptimizer:
        run = self._require_active_run(run_id).complete(now, metrics)
        return replace(
            self,
            runs=(*self.runs[:-1], run),
            next_run_time=now
            + self.configuration.run_interval_seconds(
                compaction_interval_seconds=compaction_interval_seconds
            ),
            consecutive_failures=0,
        )

    def fail_run(
        self,
        run_id: str,
        *,
        now: float,
        error: str,
        compaction_interval_seconds: float,
        compaction_failure_limit: int,
    ) -> TableOptimizer:
        run = self._require_active_run(run_id).fail(now, error)
        failures = self.consecutive_failures + 1
        configuration = self.configuration
        next_run: float | None = now + configuration.run_interval_seconds(
            compaction_interval_seconds=compaction_interval_seconds
        )
        if (
            self.optimizer_type is TableOptimizerType.COMPACTION
            and failures >= compaction_failure_limit
        ):
            configuration = configuration.disabled()
            next_run = None
        return replace(
            self,
            configuration=configuration,
            runs=(*self.runs[:-1], run),
            next_run_time=next_run,
            consecutive_failures=failures,
        )

    def cancel_active_run(self, *, now: float, reason: str) -> TableOptimizer:
        """Record a non-retryable lifecycle interruption without counting worker failure."""

        run = self.active_run
        if run is None:
            return self
        return replace(
            self,
            runs=(*self.runs[:-1], run.fail(now, reason)),
            next_run_time=now if self.configuration.enabled else None,
        )

    def _require_active_run(self, run_id: str) -> TableOptimizerRun:
        run = self.active_run
        if run is None or run.run_id != run_id:
            raise InvalidInputError(f"Optimizer run {run_id!r} is not active")
        return run


def _validate_common_configuration(document: dict[str, Any]) -> None:
    role = document.get("roleArn")
    if role is not None and not 20 <= len(str(role)) <= 2048:
        raise InvalidInputError("Table optimizer roleArn must contain 20 to 2048 characters")
    if role is not None:
        document["roleArn"] = str(role)
    vpc = document.get("vpcConfiguration")
    if vpc is not None:
        value = _mapping(vpc, "vpcConfiguration")
        connection = str(value.get("glueConnectionName", "")).strip()
        if not connection:
            raise InvalidInputError("vpcConfiguration.glueConnectionName cannot be empty")
        document["vpcConfiguration"] = {"glueConnectionName": connection}


def _compaction_configuration(value: dict[str, Any]) -> dict[str, Any]:
    strategy = str(value.get("strategy", "binpack"))
    if strategy not in {"binpack", "sort", "z-order"}:
        raise InvalidInputError(f"Unsupported compaction strategy {strategy!r}")
    return {
        "strategy": strategy,
        "minInputFiles": _positive_int(value.get("minInputFiles", 100), "minInputFiles"),
        "deleteFileThreshold": _positive_int(
            value.get("deleteFileThreshold", 1), "deleteFileThreshold"
        ),
    }


def _retention_configuration(value: dict[str, Any]) -> dict[str, Any]:
    clean_expired_files = value.get("cleanExpiredFiles", True)
    if not isinstance(clean_expired_files, bool):
        raise InvalidInputError("cleanExpiredFiles must be a Boolean")
    return {
        "snapshotRetentionPeriodInDays": _positive_int(
            value.get("snapshotRetentionPeriodInDays", 5),
            "snapshotRetentionPeriodInDays",
        ),
        "numberOfSnapshotsToRetain": _positive_int(
            value.get("numberOfSnapshotsToRetain", 1),
            "numberOfSnapshotsToRetain",
        ),
        "cleanExpiredFiles": clean_expired_files,
        "runRateInHours": _run_rate(value.get("runRateInHours", 24)),
    }


def _orphan_configuration_input(value: dict[str, Any]) -> dict[str, Any]:
    result = {
        "orphanFileRetentionPeriodInDays": _positive_int(
            value.get("orphanFileRetentionPeriodInDays", 3),
            "orphanFileRetentionPeriodInDays",
        ),
        "runRateInHours": _run_rate(value.get("runRateInHours", 24)),
    }
    if "location" in value:
        location = str(value["location"])
        _s3_uri(location, "Orphan file deletion location")
        result["location"] = location
    return result


def _bind_orphan_location(value: dict[str, Any], *, table_location: str) -> dict[str, Any]:
    location = str(value.get("location", table_location))
    table_uri = _s3_uri(table_location, "Table location")
    candidate_uri = _s3_uri(location, "Orphan file deletion location")
    table_path = table_uri.path.rstrip("/")
    candidate_path = candidate_uri.path.rstrip("/")
    if candidate_uri.netloc != table_uri.netloc or not (
        candidate_path == table_path or candidate_path.startswith(f"{table_path}/")
    ):
        raise InvalidInputError("Orphan file deletion location must be inside the table location")
    return {**copy.deepcopy(value), "location": location}


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidInputError(f"{path} must be an object")
    return copy.deepcopy(value)


def _positive_int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInputError(f"{path} must be a positive integer")
    if value <= 0:
        raise InvalidInputError(f"{path} must be a positive integer")
    return value


def _run_rate(value: object) -> int:
    parsed = _positive_int(value, "runRateInHours")
    if not 3 <= parsed <= 168:
        raise InvalidInputError("runRateInHours must be between 3 and 168")
    return parsed


def _s3_uri(value: str, path: str) -> SplitResult:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "s3"
        or not parsed.netloc
        or (parsed.path and not parsed.path.startswith("/"))
    ):
        raise InvalidInputError(f"{path} must be an absolute s3:// URI")
    if parsed.query or parsed.fragment:
        raise InvalidInputError(f"{path} cannot contain a query string or fragment")
    return parsed
