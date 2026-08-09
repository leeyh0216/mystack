"""Relational-row and immutable-domain mapping for the SQLite Glue catalog.

This module preserves unmodeled Glue request fields as canonical JSON TEXT.  It never validates
or raises Glue-domain failures: domain factories and application handlers own those semantics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from mystack.glue.domain import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    TableOptimizer,
    TableOptimizerRun,
)


def encode_document(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def decode_document(value: str) -> dict[str, Any]:
    document = json.loads(value)
    if not isinstance(document, dict):
        raise RuntimeError("SQLite Glue catalog document is not an object")
    return document


def partition_values_key(values: tuple[str, ...]) -> str:
    """Canonical full-tuple key; hashes are deliberately avoided for collision-free uniqueness."""
    return encode_document(list(values))


def database_from_row(row: tuple[Any, ...]) -> CatalogDatabase:
    catalog_id, name, definition_json, create_time = row
    return CatalogDatabase.restore(
        catalog_id=str(catalog_id),
        name=str(name),
        definition=decode_document(str(definition_json)),
        create_time=float(create_time),
    )


def table_from_row(
    row: tuple[Any, ...],
    archived_rows: Iterable[tuple[Any, ...]],
) -> CatalogTable:
    (
        catalog_id,
        database_name,
        table_name,
        definition_json,
        create_time,
        update_time,
        version_id,
    ) = row
    archived = tuple(
        CatalogTableVersion.restore(
            version_id=str(version_id),
            definition=decode_document(str(version_json)),
            create_time=float(version_create_time),
            update_time=float(version_update_time),
        )
        for _, version_id, version_json, version_create_time, version_update_time in archived_rows
    )
    return CatalogTable.restore(
        catalog_id=str(catalog_id),
        database_name=str(database_name),
        name=str(table_name),
        definition=decode_document(str(definition_json)),
        create_time=float(create_time),
        update_time=float(update_time),
        version_id=str(version_id),
        archived_versions=archived,
    )


def partition_from_row(row: tuple[Any, ...]) -> CatalogPartition:
    (
        catalog_id,
        database_name,
        table_name,
        values_json,
        definition_json,
        creation_time,
        update_time,
    ) = row
    decoded_values = json.loads(str(values_json))
    if not isinstance(decoded_values, list) or not all(
        isinstance(value, str) for value in decoded_values
    ):
        raise RuntimeError("SQLite Glue catalog partition values are invalid")
    return CatalogPartition.restore(
        catalog_id=str(catalog_id),
        database_name=str(database_name),
        table_name=str(table_name),
        values=tuple(decoded_values),
        definition=decode_document(str(definition_json)),
        creation_time=float(creation_time),
        update_time=float(update_time),
    )


def optimizer_from_rows(
    row: tuple[Any, ...],
    run_rows: Iterable[tuple[Any, ...]],
) -> TableOptimizer:
    (
        catalog_id,
        database_name,
        table_name,
        optimizer_type,
        configuration_json,
        create_time,
        update_time,
        next_run_time,
        revision,
        consecutive_failures,
    ) = row
    runs = tuple(
        TableOptimizerRun.restore(
            run_id=str(run_id),
            event_type=str(event_type),
            start_timestamp=float(start_timestamp),
            end_timestamp=None if end_timestamp is None else float(end_timestamp),
            configuration=(None if configuration is None else decode_document(str(configuration))),
            metrics=None if metrics is None else decode_document(str(metrics)),
            error=None if error is None else str(error),
        )
        for (
            _,
            run_id,
            event_type,
            start_timestamp,
            end_timestamp,
            configuration,
            metrics,
            error,
        ) in run_rows
    )
    return TableOptimizer.restore(
        catalog_id=str(catalog_id),
        database_name=str(database_name),
        table_name=str(table_name),
        optimizer_type=str(optimizer_type),
        configuration=decode_document(str(configuration_json)),
        create_time=float(create_time),
        update_time=float(update_time),
        next_run_time=None if next_run_time is None else float(next_run_time),
        revision=int(revision),
        runs=runs,
        consecutive_failures=int(consecutive_failures),
    )


def partition_key_rows(value: CatalogTable) -> tuple[tuple[int, str, str, str], ...]:
    """Project safe hints without validating arbitrary Glue input prematurely."""
    raw_keys = value.definition.get("PartitionKeys", ())
    if not isinstance(raw_keys, list | tuple):
        return ()
    rows: list[tuple[int, str, str, str]] = []
    for ordinal, raw in enumerate(raw_keys):
        document = raw if isinstance(raw, dict) else {"value": raw}
        rows.append(
            (
                ordinal,
                encode_document(document),
                str(document.get("Name", "")),
                str(document.get("Type", "string")),
            )
        )
    return tuple(rows)
