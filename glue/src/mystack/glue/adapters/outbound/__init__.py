"""Glue infrastructure adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from mystack.glue.adapters.outbound.iceberg_metadata import S3IcebergMetadataStore
from mystack.glue.adapters.outbound.sqlite_catalog import (
    CatalogTransactionHook,
    SqliteCatalogRepository,
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
    "CatalogTransactionHook",
    "S3IcebergMetadataStore",
    "SQLiteRuntimeCapabilityError",
    "SQLiteRuntimeVerification",
    "SQLiteRuntimeVerifier",
    "SparkTableOptimizerExecutor",
    "SparkTableOptimizerExecutorSettings",
    "SqliteCatalogRepository",
    "SystemClock",
    "SystemIdentifierGenerator",
]
