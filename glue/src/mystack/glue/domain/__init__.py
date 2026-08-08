"""Framework-independent Glue Data Catalog domain.

Reference: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
"""

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
    CatalogState,
    CatalogTable,
    CatalogTableVersion,
    PartitionValues,
)
from mystack.glue.domain.open_table_format import (
    IcebergOpenTableFormatPlanner,
    PlannedIcebergTable,
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
    "VersionMismatchError",
]
