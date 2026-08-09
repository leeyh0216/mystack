"""Executable Glue application-port responsibility boundaries.

Reference: https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import inspect
from pathlib import Path

from mystack.glue.adapters.outbound import SqliteCatalogRepository
from mystack.glue.application.batch import PartitionBatchHandler
from mystack.glue.application.catalog_ports import (
    CatalogQueryPort,
    CatalogReadPort,
    CatalogTransaction,
    CatalogWritePort,
)
from mystack.glue.application.database import DatabaseCommands, DatabaseQueries
from mystack.glue.application.initialization import CatalogInitializer
from mystack.glue.application.open_table_format import OpenTableFormatCommands
from mystack.glue.application.pagination import Paginator
from mystack.glue.application.partition import (
    PartitionCommands,
    PartitionQueries,
    PartitionTargetResolver,
)
from mystack.glue.application.table import TableCommands, TableQueries, TableVersionQueries
from mystack.glue.application.table_optimizer import TableOptimizerCommands, TableOptimizerQueries


def _public_methods(value: type) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(value, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def test_application_handlers_have_one_explicit_responsibility() -> None:
    assert _public_methods(DatabaseCommands) == {"create", "delete", "update"}
    assert _public_methods(DatabaseQueries) == {"get", "list"}
    assert _public_methods(TableCommands) == {"create", "delete", "update"}
    assert _public_methods(TableQueries) == {"get", "list"}
    assert _public_methods(TableVersionQueries) == {"get", "list"}
    assert _public_methods(OpenTableFormatCommands) == {"create", "update"}
    assert _public_methods(PartitionCommands) == {"create", "delete", "update"}
    assert _public_methods(PartitionQueries) == {"get", "list"}
    assert _public_methods(PartitionTargetResolver) == {"require"}
    assert _public_methods(PartitionBatchHandler) == {"create", "delete", "get", "update"}
    assert _public_methods(CatalogInitializer) == {"initialize"}
    assert _public_methods(Paginator) == {
        "complete_keyset",
        "context",
        "page",
        "prepare",
        "prepare_keyset",
    }
    assert _public_methods(TableOptimizerCommands) == {
        "claim_due",
        "complete",
        "create",
        "delete",
        "fail",
        "mark_in_progress",
        "recover_interrupted",
        "update",
    }
    assert _public_methods(TableOptimizerQueries) == {
        "batch_get",
        "get",
        "is_current",
        "list_runs",
    }


def test_catalog_port_capabilities_are_typed_and_segregated() -> None:
    assert _public_methods(CatalogReadPort) == {
        "find_database",
        "find_optimizer",
        "find_partition",
        "find_table",
        "list_active_optimizers",
        "list_due_optimizers",
        "list_optimizers_for_database",
        "list_optimizers_for_table",
    }
    assert _public_methods(CatalogQueryPort) == {
        "count_databases",
        "count_partitions",
        "count_tables",
        "first_partition",
        "page_databases",
        "page_partitions",
        "page_tables",
    }
    assert _public_methods(CatalogWritePort) == {"initialize", "transaction"}
    assert _public_methods(CatalogTransaction) == {
        "delete_database",
        "delete_optimizer",
        "delete_partition",
        "delete_table",
        "find_database",
        "find_optimizer",
        "find_partition",
        "find_table",
        "insert_database",
        "insert_optimizer",
        "insert_partition",
        "insert_table",
        "list_active_optimizers",
        "list_due_optimizers",
        "list_optimizers_for_database",
        "list_optimizers_for_table",
        "replace_database",
        "replace_optimizer",
        "replace_partition",
        "replace_table",
    }
    assert _public_methods(SqliteCatalogRepository) == (
        _public_methods(CatalogReadPort)
        | _public_methods(CatalogQueryPort)
        | _public_methods(CatalogWritePort)
    )


def test_legacy_catalog_aggregate_and_json_store_do_not_exist_in_production_source() -> None:
    root = Path(__file__).parents[1] / "src" / "mystack" / "glue"
    assert not (root / "domain" / "catalog_state.py").exists()
    assert not (root / "domain" / "repositories.py").exists()
    assert not (root / "adapters" / "outbound" / "repository.py").exists()
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*.py")
        if "partition_expression/generated" not in str(path)
    )
    for forbidden in ("CatalogState", "JsonCatalog", "InMemoryCatalog", ".snapshot()"):
        assert forbidden not in production
