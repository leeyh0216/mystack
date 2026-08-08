"""Durable Data Catalog adapter contract.

Delete/cascade semantics reference:
https://docs.aws.amazon.com/glue/latest/dg/tables-described.html
"""

from pathlib import Path

from mystack.glue.adapters.outbound import JsonCatalogRepository
from mystack.glue.domain import CatalogDatabase, CatalogTable


async def test_catalog_state_survives_repository_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "catalog.json"
    first = JsonCatalogRepository(state_file)
    await first.create_database(CatalogDatabase("account", "db", {"Name": "db"}, 1.0))
    await first.create_table(
        CatalogTable(
            "account",
            "db",
            "table",
            {"Name": "table", "StorageDescriptor": {"Columns": []}},
            1.0,
            1.0,
            "0",
        )
    )

    restarted = JsonCatalogRepository(state_file)

    assert (await restarted.get_database("account", "db")).definition == {"Name": "db"}
    assert (await restarted.get_table("account", "db", "table")).version_id == "0"
