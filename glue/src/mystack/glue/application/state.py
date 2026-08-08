"""Catalog collection lookups and multi-record application policies.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
"""

from __future__ import annotations

from mystack.glue.domain import (
    CatalogDatabase,
    CatalogName,
    CatalogPartition,
    CatalogState,
    CatalogTable,
    EntityNotFoundError,
)


def name(value: object) -> str:
    return CatalogName.parse(value).value


def database(state: CatalogState, catalog_id: str, database_name: str) -> CatalogDatabase:
    value = state.databases.get((catalog_id, database_name))
    if value is None:
        raise EntityNotFoundError(f"Database {database_name!r} does not exist")
    return value


def table(
    state: CatalogState,
    catalog_id: str,
    database_name: str,
    table_name: str,
) -> CatalogTable:
    value = state.tables.get((catalog_id, database_name, table_name))
    if value is None:
        raise EntityNotFoundError(f"Table {database_name}.{table_name} does not exist")
    return value


def partition(
    state: CatalogState,
    catalog_id: str,
    database_name: str,
    table_name: str,
    values: tuple[str, ...],
) -> CatalogPartition:
    value = state.partitions.get((catalog_id, database_name, table_name, values))
    if value is None:
        raise EntityNotFoundError(f"Partition {list(values)!r} does not exist")
    return value


def rename_database_children(
    state: CatalogState,
    catalog_id: str,
    old_name: str,
    new_name: str,
) -> None:
    for key in [value for value in state.tables if value[:2] == (catalog_id, old_name)]:
        child = state.tables.pop(key).move_database(new_name)
        state.tables[(catalog_id, new_name, child.name)] = child
    for key in [value for value in state.partitions if value[:2] == (catalog_id, old_name)]:
        child = state.partitions.pop(key).move_database(new_name)
        state.partitions[partition_key(child)] = child


def rename_table_partitions(
    state: CatalogState,
    catalog_id: str,
    database_name: str,
    old_name: str,
    new_name: str,
) -> None:
    prefix = (catalog_id, database_name, old_name)
    for key in [value for value in state.partitions if value[:3] == prefix]:
        child = state.partitions.pop(key).move_table(new_name)
        state.partitions[partition_key(child)] = child


def partition_key(
    value: CatalogPartition,
) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        value.catalog_id,
        value.database_name,
        value.table_name,
        value.values,
    )
