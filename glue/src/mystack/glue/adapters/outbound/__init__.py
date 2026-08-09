"""Glue infrastructure adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from mystack.glue.adapters.outbound.iceberg_metadata import S3IcebergMetadataStore
from mystack.glue.adapters.outbound.repository import (
    CatalogStateStore,
    CatalogStateSynchronizer,
    FileCatalogStateSynchronizer,
    InMemoryCatalogRepository,
    JsonCatalogRepository,
    JsonCatalogStateStore,
    LocalCatalogStateSynchronizer,
    TransactionalCatalogRepository,
    VolatileCatalogStateStore,
)
from mystack.glue.adapters.outbound.sqlite_runtime import (
    SQLiteRuntimeCapabilityError,
    SQLiteRuntimeVerification,
    SQLiteRuntimeVerifier,
)
from mystack.glue.adapters.outbound.system import SystemClock, SystemIdentifierGenerator
from mystack.glue.adapters.outbound.table_optimizer_executor import (
    SparkTableOptimizerExecutor,
    SparkTableOptimizerExecutorSettings,
)

__all__ = [
    "CatalogStateStore",
    "CatalogStateSynchronizer",
    "FileCatalogStateSynchronizer",
    "InMemoryCatalogRepository",
    "JsonCatalogRepository",
    "JsonCatalogStateStore",
    "LocalCatalogStateSynchronizer",
    "S3IcebergMetadataStore",
    "SQLiteRuntimeCapabilityError",
    "SQLiteRuntimeVerification",
    "SQLiteRuntimeVerifier",
    "SparkTableOptimizerExecutor",
    "SparkTableOptimizerExecutorSettings",
    "SystemClock",
    "SystemIdentifierGenerator",
    "TransactionalCatalogRepository",
    "VolatileCatalogStateStore",
]
