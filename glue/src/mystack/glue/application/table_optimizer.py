"""Managed Glue Iceberg table-optimizer commands, queries, and work claims.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
- https://docs.aws.amazon.com/glue/latest/dg/optimizer-notes.html
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.catalog_identity import name, table
from mystack.glue.application.catalog_identity import optimizer as require_optimizer
from mystack.glue.application.catalog_ports import CatalogReadPort, CatalogWritePort
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.ports import Clock, IdentifierGenerator
from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork
from mystack.glue.domain import (
    AlreadyExistsError,
    InvalidInputError,
    TableOptimizer,
    TableOptimizerConfigurationDraft,
    TableOptimizerKey,
    TableOptimizerRun,
    TableOptimizerType,
)
from mystack.glue.domain.errors import GlueDomainError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TableOptimizerPolicy:
    initial_delay_seconds: float
    compaction_interval_seconds: float
    history_limit: int
    compaction_failure_limit: int

    def __post_init__(self) -> None:
        if self.initial_delay_seconds < 0:
            raise ValueError("Optimizer initial delay cannot be negative")
        if self.compaction_interval_seconds <= 0:
            raise ValueError("Optimizer compaction interval must be positive")
        if self.history_limit <= 0:
            raise ValueError("Optimizer history limit must be positive")
        if self.compaction_failure_limit <= 0:
            raise ValueError("Optimizer compaction failure limit must be positive")


@dataclass(frozen=True, slots=True)
class BatchTableOptimizerFailure:
    catalog_id: str
    database_name: str
    table_name: str
    optimizer_type: str
    error: GlueDomainError


@dataclass(frozen=True, slots=True)
class BatchTableOptimizerResult:
    optimizers: tuple[TableOptimizer, ...]
    failures: tuple[BatchTableOptimizerFailure, ...]


class TableOptimizerCommands:
    def __init__(
        self,
        catalog: CatalogWritePort,
        clock: Clock,
        identifiers: IdentifierGenerator,
        policy: TableOptimizerPolicy,
    ) -> None:
        self._catalog = catalog
        self._clock = clock
        self._identifiers = identifiers
        self._policy = policy

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: object,
        configuration: object,
    ) -> None:
        normalized_database, normalized_table, parsed_type = _identity(
            database_name,
            table_name,
            optimizer_type,
        )
        key = (catalog_id, normalized_database, normalized_table, parsed_type.value)
        configuration_draft = TableOptimizerConfigurationDraft.parse(
            parsed_type,
            configuration,
        )
        _log_boundary("create", "before", key, side_effect=True)
        async with self._catalog.transaction(
            operation="create-table-optimizer",
            resource_key=key,
        ) as transaction:
            catalog_table = await table(
                transaction, catalog_id, normalized_database, normalized_table
            )
            table_location = _optimizer_table_location(catalog_table.definition, parsed_type)
            normalized_configuration = configuration_draft.bind(
                table_location=table_location,
            )
            if (
                await transaction.find_optimizer(
                    catalog_id,
                    normalized_database,
                    normalized_table,
                    parsed_type.value,
                )
                is not None
            ):
                raise AlreadyExistsError(
                    f"Table optimizer {parsed_type.value!r} already exists for "
                    f"{normalized_database}.{normalized_table}"
                )
            value = TableOptimizer.create(
                catalog_id=catalog_id,
                database_name=normalized_database,
                table_name=normalized_table,
                optimizer_type=parsed_type,
                configuration=normalized_configuration,
                now=self._clock.now(),
                initial_delay_seconds=self._policy.initial_delay_seconds,
            )
            if not await transaction.insert_optimizer(value):
                raise AlreadyExistsError(
                    f"Table optimizer {parsed_type.value!r} already exists for "
                    f"{normalized_database}.{normalized_table}"
                )
        _log_boundary("create", "after", key, side_effect=True)

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: object,
        configuration: object,
    ) -> None:
        normalized_database, normalized_table, parsed_type = _identity(
            database_name,
            table_name,
            optimizer_type,
        )
        key = (catalog_id, normalized_database, normalized_table, parsed_type.value)
        configuration_draft = TableOptimizerConfigurationDraft.parse(
            parsed_type,
            configuration,
        )
        _log_boundary("update", "before", key, side_effect=True)
        async with self._catalog.transaction(
            operation="update-table-optimizer",
            resource_key=key,
        ) as transaction:
            catalog_table = await table(
                transaction, catalog_id, normalized_database, normalized_table
            )
            table_location = _optimizer_table_location(catalog_table.definition, parsed_type)
            normalized_configuration = configuration_draft.bind(
                table_location=table_location,
            )
            current = await require_optimizer(
                transaction,
                catalog_id,
                normalized_database,
                normalized_table,
                parsed_type.value,
            )
            if current.active_run is not None:
                current = current.cancel_active_run(
                    now=self._clock.now(),
                    reason="Table optimizer configuration changed during execution",
                )
            revised = current.revise(
                normalized_configuration,
                now=self._clock.now(),
                initial_delay_seconds=self._policy.initial_delay_seconds,
            )
            if not await transaction.replace_optimizer(current, revised):
                raise RuntimeError("SQLite catalog optimizer changed during update")
        _log_boundary("update", "after", key, side_effect=True)

    async def delete(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: object,
    ) -> None:
        normalized_database, normalized_table, parsed_type = _identity(
            database_name,
            table_name,
            optimizer_type,
        )
        key = (catalog_id, normalized_database, normalized_table, parsed_type.value)
        _log_boundary("delete", "before", key, side_effect=True)
        async with self._catalog.transaction(
            operation="delete-table-optimizer",
            resource_key=key,
        ) as transaction:
            await table(transaction, catalog_id, normalized_database, normalized_table)
            current = await require_optimizer(
                transaction,
                catalog_id,
                normalized_database,
                normalized_table,
                parsed_type.value,
            )
            if not await transaction.delete_optimizer(current):
                raise RuntimeError("SQLite catalog optimizer changed during delete")
        _log_boundary("delete", "after", key, side_effect=True)

    async def recover_interrupted(self, reason: str) -> int:
        recovered = 0
        async with self._catalog.transaction(
            operation="recover-table-optimizer-runs",
            resource_key=("all-active-optimizers",),
        ) as transaction:
            for current in await transaction.list_active_optimizers():
                active = current.active_run
                if active is None:
                    continue
                revised = current.fail_run(
                    active.run_id,
                    now=self._clock.now(),
                    error=reason,
                    compaction_interval_seconds=self._policy.compaction_interval_seconds,
                    compaction_failure_limit=self._policy.compaction_failure_limit,
                )
                if not await transaction.replace_optimizer(current, revised):
                    continue
                recovered += 1
                _log_boundary("recover", "after", current.key, side_effect=True)
        return recovered

    async def claim_due(self, maximum: int) -> list[TableOptimizerWork]:
        if maximum <= 0:
            return []
        now = self._clock.now()
        work: list[TableOptimizerWork] = []
        async with self._catalog.transaction(
            operation="claim-due-table-optimizer-runs",
            resource_key=("due-optimizers", maximum),
        ) as transaction:
            for current in await transaction.list_due_optimizers(now, maximum):
                key = current.key
                if (
                    not current.configuration.enabled
                    or current.active_run is not None
                    or current.next_run_time is None
                    or current.next_run_time > now
                ):
                    continue
                catalog_table = await table(transaction, *key[:3])
                location = _optimizer_table_location(
                    catalog_table.definition,
                    current.optimizer_type,
                )
                run_id = self._identifiers.new()
                claimed = current.claim(run_id, now, history_limit=self._policy.history_limit)
                if not await transaction.replace_optimizer(current, claimed):
                    continue
                work.append(
                    TableOptimizerWork(
                        key=key,
                        run_id=run_id,
                        configuration_revision=current.revision,
                        configuration=current.configuration.document,
                        table_location=location,
                        optimizer_create_time=current.create_time,
                    )
                )
                _log_boundary("claim", "after", key, run_id=run_id, side_effect=True)
        return work

    async def mark_in_progress(self, work: TableOptimizerWork) -> bool:
        return await self._transition(work, "in-progress", None)

    async def complete(self, work: TableOptimizerWork, metrics: dict[str, Any]) -> bool:
        return await self._transition(work, "complete", metrics)

    async def fail(self, work: TableOptimizerWork, error: str) -> bool:
        return await self._transition(work, "fail", str(error))

    async def _transition(
        self,
        work: TableOptimizerWork,
        transition: str,
        detail: object,
    ) -> bool:
        _log_boundary(transition, "before", work.key, run_id=work.run_id, side_effect=True)
        async with self._catalog.transaction(
            operation=f"{transition}-table-optimizer-run",
            resource_key=work.key,
        ) as transaction:
            current = await transaction.find_optimizer(*work.key)
            if (
                current is None
                or current.revision != work.configuration_revision
                or current.active_run is None
                or current.active_run.run_id != work.run_id
            ):
                _log_boundary(
                    transition,
                    "stale",
                    work.key,
                    run_id=work.run_id,
                    side_effect=False,
                )
                return False
            if transition == "in-progress":
                revised = current.mark_in_progress(work.run_id)
            elif transition == "complete":
                revised = current.complete_run(
                    work.run_id,
                    now=self._clock.now(),
                    metrics=dict(detail) if isinstance(detail, dict) else {},
                    compaction_interval_seconds=self._policy.compaction_interval_seconds,
                )
            else:
                revised = current.fail_run(
                    work.run_id,
                    now=self._clock.now(),
                    error=str(detail),
                    compaction_interval_seconds=self._policy.compaction_interval_seconds,
                    compaction_failure_limit=self._policy.compaction_failure_limit,
                )
            if not await transaction.replace_optimizer(current, revised):
                _log_boundary(
                    transition,
                    "stale",
                    work.key,
                    run_id=work.run_id,
                    side_effect=False,
                )
                return False
        _log_boundary(transition, "after", work.key, run_id=work.run_id, side_effect=True)
        return True


class TableOptimizerQueries:
    def __init__(self, catalog: CatalogReadPort, paginator: Paginator) -> None:
        self._catalog = catalog
        self._paginator = paginator

    async def get(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: object,
    ) -> TableOptimizer:
        normalized_database, normalized_table, parsed_type = _identity(
            database_name,
            table_name,
            optimizer_type,
        )
        key = (catalog_id, normalized_database, normalized_table, parsed_type.value)
        _log_boundary("get", "before", key, side_effect=False)
        await table(self._catalog, catalog_id, normalized_database, normalized_table)
        value = await require_optimizer(
            self._catalog,
            catalog_id,
            normalized_database,
            normalized_table,
            parsed_type.value,
        )
        _log_boundary("get", "after", key, side_effect=False)
        return value

    async def batch_get(
        self,
        entries: list[tuple[str, str, str, object]],
    ) -> BatchTableOptimizerResult:
        if len(entries) > 20:
            raise InvalidInputError("BatchGetTableOptimizer accepts at most 20 entries")
        values: list[TableOptimizer] = []
        failures: list[BatchTableOptimizerFailure] = []
        for catalog_id, database_name, table_name, optimizer_type in entries:
            try:
                values.append(await self.get(catalog_id, database_name, table_name, optimizer_type))
            except GlueDomainError as error:
                failures.append(
                    BatchTableOptimizerFailure(
                        catalog_id=str(catalog_id),
                        database_name=str(database_name),
                        table_name=str(table_name),
                        optimizer_type=str(optimizer_type),
                        error=error,
                    )
                )
        return BatchTableOptimizerResult(tuple(values), tuple(failures))

    async def list_runs(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        optimizer_type: object,
        *,
        next_token: str | None,
        max_results: int | None,
    ) -> tuple[list[TableOptimizerRun], str | None]:
        page = self._paginator.prepare(next_token, max_results)
        value = await self.get(catalog_id, database_name, table_name, optimizer_type)
        return page.apply(list(reversed(value.runs)))

    async def is_current(self, work: TableOptimizerWork) -> bool:
        current = await self._catalog.find_optimizer(*work.key)
        return bool(
            current is not None
            and current.revision == work.configuration_revision
            and current.active_run is not None
            and current.active_run.run_id == work.run_id
        )


def _identity(
    database_name: str,
    table_name: str,
    optimizer_type: object,
) -> tuple[str, str, TableOptimizerType]:
    return name(database_name), name(table_name), TableOptimizerType.parse(optimizer_type)


def _optimizer_table_location(
    definition: dict[str, Any],
    optimizer_type: TableOptimizerType,
) -> str:
    parameters = definition.get("Parameters")
    if not isinstance(parameters, dict) or str(parameters.get("table_type", "")).upper() != (
        "ICEBERG"
    ):
        raise InvalidInputError("Table optimizers require an Iceberg table")
    descriptor = definition.get("StorageDescriptor")
    if not isinstance(descriptor, dict) or not str(descriptor.get("Location", "")).strip():
        raise InvalidInputError("Iceberg table StorageDescriptor.Location is required")
    location = str(descriptor["Location"])
    if optimizer_type is TableOptimizerType.COMPACTION:
        file_format = str(parameters.get("write.format.default", "parquet")).casefold()
        if file_format != "parquet":
            raise InvalidInputError("Glue Iceberg compaction supports only Parquet tables")
    return location


def _log_boundary(
    operation: str,
    phase: str,
    key: TableOptimizerKey,
    *,
    run_id: str | None = None,
    side_effect: bool,
) -> None:
    log_event(
        _LOGGER,
        logging.DEBUG,
        f"glue.table_optimizer.{operation}.{phase}",
        resource_fingerprint=hashlib.sha256(repr(key).encode()).hexdigest()[:16],
        optimizer_type=key[3],
        run_id=run_id,
        side_effect=side_effect,
        fix_hint=(
            "If a newer boto3, Glue Spark catalog, or Iceberg client changes this boundary, "
            "inspect the table-optimizer inbound family before changing domain transitions."
        ),
    )
