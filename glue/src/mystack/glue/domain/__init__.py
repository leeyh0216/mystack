"""Framework-independent Glue Data Catalog domain.

Reference: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
"""

from .errors import (
    AlreadyExistsError,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)
from .model import (
    CatalogDatabase,
    CatalogDocument,
    CatalogName,
    CatalogPartition,
    CatalogState,
    CatalogTable,
    CatalogTableVersion,
    PartitionValues,
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
    "InvalidInputError",
    "PartitionValues",
    "VersionMismatchError",
]
