"""Data Catalog aggregates that preserve service-model fields losslessly.

AWS documents that the Data Catalog does not validate type strings. Mystack therefore
preserves Column.Type and nested StorageDescriptor data rather than narrowing them.
Reference: https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DatabaseKey = tuple[str, str]
TableKey = tuple[str, str, str]
PartitionKey = tuple[str, str, str, tuple[str, ...]]


@dataclass(slots=True)
class CatalogDatabase:
    catalog_id: str
    name: str
    definition: dict[str, Any]
    create_time: float


@dataclass(slots=True)
class CatalogTableVersion:
    version_id: str
    definition: dict[str, Any]
    create_time: float
    update_time: float


@dataclass(slots=True)
class CatalogTable:
    catalog_id: str
    database_name: str
    name: str
    definition: dict[str, Any]
    create_time: float
    update_time: float
    version_id: str
    archived_versions: list[CatalogTableVersion] = field(default_factory=list)


@dataclass(slots=True)
class CatalogPartition:
    catalog_id: str
    database_name: str
    table_name: str
    values: tuple[str, ...]
    definition: dict[str, Any]
    creation_time: float
    update_time: float


@dataclass(slots=True)
class CatalogState:
    """One candidate or committed Data Catalog state."""

    revision: int = 0
    databases: dict[DatabaseKey, CatalogDatabase] = field(default_factory=dict)
    tables: dict[TableKey, CatalogTable] = field(default_factory=dict)
    partitions: dict[PartitionKey, CatalogPartition] = field(default_factory=dict)
