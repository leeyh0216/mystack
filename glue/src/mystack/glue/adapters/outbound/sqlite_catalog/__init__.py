"""SQLite-only Glue Data Catalog adapter.

The adapter is intentionally the only Glue layer that imports a DB-API implementation.  It maps
typed application ports to normalized SQLite rows without deciding Glue domain failures.
"""

from mystack.glue.adapters.outbound.sqlite_catalog.repository import (
    CatalogTransactionHook,
    SqliteCatalogRepository,
)

__all__ = ["CatalogTransactionHook", "SqliteCatalogRepository"]
