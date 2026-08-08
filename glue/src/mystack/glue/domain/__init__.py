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
    CatalogPartition,
    CatalogState,
    CatalogTable,
    CatalogTableVersion,
)

__all__ = [
    "AlreadyExistsError",
    "CatalogDatabase",
    "CatalogPartition",
    "CatalogState",
    "CatalogTable",
    "CatalogTableVersion",
    "EntityNotFoundError",
    "InvalidInputError",
    "VersionMismatchError",
]
