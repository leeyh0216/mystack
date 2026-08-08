"""Glue catalog initialization use case.

Reference: https://docs.aws.amazon.com/glue/latest/dg/start-data-catalog.html
"""

from __future__ import annotations

from mystack.glue.application.database import DatabaseCommands, DatabaseQueries
from mystack.glue.domain import AlreadyExistsError, EntityNotFoundError


class CatalogInitializer:
    def __init__(
        self,
        databases: DatabaseCommands,
        queries: DatabaseQueries,
        *,
        catalog_id: str,
        create_default_database: bool,
    ) -> None:
        self._databases = databases
        self._queries = queries
        self._catalog_id = catalog_id
        self._create_default_database = create_default_database

    async def initialize(self) -> None:
        if not self._create_default_database:
            return
        try:
            await self._queries.get(self._catalog_id, "default")
            return
        except EntityNotFoundError:
            try:
                await self._databases.create(self._catalog_id, {"Name": "default"})
            except AlreadyExistsError:
                pass
