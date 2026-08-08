"""Framework-independent Glue Data Catalog domain.

Reference: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
"""

from mystack.glue.domain.catalog_state import CatalogState
from mystack.glue.domain.errors import (
    AlreadyExistsError,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)
from mystack.glue.domain.model import (
    CatalogDatabase,
    CatalogDocument,
    CatalogName,
    CatalogPartition,
    CatalogTable,
    CatalogTableVersion,
    PartitionValues,
)
from mystack.glue.domain.open_table_format import (
    IcebergOpenTableFormatPlanner,
    PlannedIcebergTable,
)
from mystack.glue.domain.table_optimizer import (
    TableOptimizer,
    TableOptimizerConfiguration,
    TableOptimizerConfigurationDraft,
    TableOptimizerEventType,
    TableOptimizerKey,
    TableOptimizerRun,
    TableOptimizerType,
)

__all__ = [
    "AlreadyExistsError",
    "CatalogDatabase",
    "CatalogDocument",
    "CatalogName",
    "CatalogPartition",
    "CatalogState",
    "CatalogTable",
    "CatalogTableVersion",
    "EntityNotFoundError",
    "IcebergOpenTableFormatPlanner",
    "InvalidInputError",
    "PartitionValues",
    "PlannedIcebergTable",
    "TableOptimizer",
    "TableOptimizerConfiguration",
    "TableOptimizerConfigurationDraft",
    "TableOptimizerEventType",
    "TableOptimizerKey",
    "TableOptimizerRun",
    "TableOptimizerType",
    "VersionMismatchError",
]
