"""Application-level Catalog identity lookups and Glue error mapping.

These helpers deliberately map neutral port results to domain errors.  Storage adapters must not
choose which Glue validation error wins when multiple conditions are invalid.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
"""

from __future__ import annotations

from mystack.glue.application.catalog_ports import CatalogReadPort
from mystack.glue.domain import (
    CatalogDatabase,
    CatalogName,
    CatalogPartition,
    CatalogTable,
    EntityNotFoundError,
    TableOptimizer,
)


def name(value: object) -> str:
    return CatalogName.parse(value).value


async def database(
    reader: CatalogReadPort,
    catalog_id: str,
    database_name: str,
) -> CatalogDatabase:
    value = await reader.find_database(catalog_id, database_name)
    if value is None:
        raise EntityNotFoundError(f"Database {database_name!r} does not exist")
    return value


async def table(
    reader: CatalogReadPort,
    catalog_id: str,
    database_name: str,
    table_name: str,
) -> CatalogTable:
    value = await reader.find_table(catalog_id, database_name, table_name)
    if value is None:
        raise EntityNotFoundError(f"Table {database_name}.{table_name} does not exist")
    return value


async def partition(
    reader: CatalogReadPort,
    catalog_id: str,
    database_name: str,
    table_name: str,
    values: tuple[str, ...],
) -> CatalogPartition:
    value = await reader.find_partition(catalog_id, database_name, table_name, values)
    if value is None:
        raise EntityNotFoundError(f"Partition {list(values)!r} does not exist")
    return value


async def optimizer(
    reader: CatalogReadPort,
    catalog_id: str,
    database_name: str,
    table_name: str,
    optimizer_type: str,
) -> TableOptimizer:
    value = await reader.find_optimizer(catalog_id, database_name, table_name, optimizer_type)
    if value is None:
        raise EntityNotFoundError(
            f"Table optimizer {optimizer_type!r} does not exist for {database_name}.{table_name}"
        )
    return value
