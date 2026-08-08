"""Executable responsibility boundaries for focused Glue handlers.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import inspect

from mystack.glue.adapters.outbound import (
    InMemoryCatalogRepository,
    JsonCatalogRepository,
    TransactionalCatalogRepository,
)
from mystack.glue.application.batch import PartitionBatchHandler
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
    assert _public_methods(Paginator) == {"page", "prepare"}


def test_repositories_expose_collection_transaction_capabilities_only() -> None:
    expected = {"snapshot", "transaction"}
    for repository in (
        InMemoryCatalogRepository,
        JsonCatalogRepository,
        TransactionalCatalogRepository,
    ):
        assert _public_methods(repository) == expected
