"""One isolated Glue Data Catalog candidate or committed aggregate collection.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mystack.glue.domain.model import (
    CatalogDatabase,
    CatalogPartition,
    CatalogTable,
    DatabaseKey,
    PartitionKey,
    TableKey,
)
from mystack.glue.domain.table_optimizer import TableOptimizer, TableOptimizerKey


@dataclass(slots=True)
class CatalogState:
    """Aggregate collection kept outside its child value modules to prevent import cycles."""

    revision: int = 0
    databases: dict[DatabaseKey, CatalogDatabase] = field(default_factory=dict)
    tables: dict[TableKey, CatalogTable] = field(default_factory=dict)
    partitions: dict[PartitionKey, CatalogPartition] = field(default_factory=dict)
    optimizers: dict[TableOptimizerKey, TableOptimizer] = field(default_factory=dict)
