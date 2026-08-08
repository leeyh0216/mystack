"""Atomic Glue Open Table Format catalog use cases.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html
- https://iceberg.apache.org/spec/#metastore-serialization
"""

from __future__ import annotations

import json
import logging

from mystack.aws_protocol.observability import log_event, payload_fingerprint
from mystack.glue.application.database import DatabaseQueries
from mystack.glue.application.ports import Clock, IcebergMetadataStore, IdentifierGenerator
from mystack.glue.application.table import TableCommands, TableQueries
from mystack.glue.domain import (
    AlreadyExistsError,
    CatalogTable,
    EntityNotFoundError,
    IcebergOpenTableFormatPlanner,
    InvalidInputError,
)

_LOGGER = logging.getLogger(__name__)


class OpenTableFormatCommands:
    """Coordinate object storage and catalog publication without leaking adapters inward."""

    def __init__(
        self,
        *,
        databases: DatabaseQueries,
        tables: TableQueries,
        table_commands: TableCommands,
        metadata_store: IcebergMetadataStore,
        identifiers: IdentifierGenerator,
        clock: Clock,
        planner: IcebergOpenTableFormatPlanner,
    ) -> None:
        self._databases = databases
        self._tables = tables
        self._table_commands = table_commands
        self._metadata_store = metadata_store
        self._identifiers = identifiers
        self._clock = clock
        self._planner = planner

    async def create(
        self,
        catalog_id: str,
        database_name: str,
        table_name: object,
        iceberg_input: object,
    ) -> CatalogTable:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.create.validate.before",
            catalog_id=catalog_id,
            database=database_name,
            side_effect=False,
        )
        plan = self._planner.create(
            table_name=table_name,
            iceberg_input=iceberg_input,
            now_ms=self._now_ms(),
            identifier=self._identifiers.new(),
        )
        await self._databases.get(catalog_id, database_name)
        try:
            await self._tables.get(catalog_id, database_name, plan.table_definition["Name"])
        except EntityNotFoundError:
            pass
        else:
            raise AlreadyExistsError(
                f"Table {database_name}.{plan.table_definition['Name']} already exists"
            )
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.create.validate.after",
            catalog_id=catalog_id,
            database=database_name,
            table=plan.table_definition["Name"],
            metadata_location_fingerprint=_fingerprint(plan.metadata_location),
            side_effect=False,
        )
        await self._write_candidate(plan.metadata_location, plan.metadata)
        try:
            value = await self._table_commands.create(
                catalog_id,
                database_name,
                plan.table_definition,
            )
        except BaseException:
            await self._compensate(plan.metadata_location)
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.create.published",
            catalog_id=catalog_id,
            database=database_name,
            table=value.name,
            version_id=value.version_id,
            metadata_location_fingerprint=_fingerprint(plan.metadata_location),
            side_effect=True,
        )
        return value

    async def update(
        self,
        catalog_id: str,
        database_name: str,
        table_name: str,
        update_input: object,
        *,
        version_id: str | None,
        skip_archive: bool,
    ) -> None:
        current = await self._tables.get(catalog_id, database_name, table_name)
        definition = current.definition
        parameters = definition.get("Parameters", {})
        if not isinstance(parameters, dict) or str(parameters.get("table_type", "")).upper() != (
            "ICEBERG"
        ):
            raise InvalidInputError("UpdateOpenTableFormatInput requires an existing Iceberg table")
        current_location = parameters.get("metadata_location")
        if not isinstance(current_location, str) or not current_location:
            raise InvalidInputError("Existing Iceberg table has no metadata_location")
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.update.read.before",
            catalog_id=catalog_id,
            database=database_name,
            table=current.name,
            version_id=current.version_id,
            metadata_location_fingerprint=_fingerprint(current_location),
            side_effect=True,
        )
        current_metadata = await self._metadata_store.read(current_location)
        plan = self._planner.update(
            table_definition=definition,
            current_metadata_location=current_location,
            current_metadata=current_metadata,
            update_input=update_input,
            now_ms=self._now_ms(),
            identifier=self._identifiers.new(),
        )
        await self._write_candidate(plan.metadata_location, plan.metadata)
        try:
            await self._table_commands.update(
                catalog_id,
                database_name,
                current.name,
                plan.table_definition,
                version_id=current.version_id if version_id is None else version_id,
                skip_archive=skip_archive,
            )
        except BaseException:
            await self._compensate(plan.metadata_location)
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.update.published",
            catalog_id=catalog_id,
            database=database_name,
            table=current.name,
            previous_version_id=current.version_id,
            metadata_location_fingerprint=_fingerprint(plan.metadata_location),
            side_effect=True,
        )

    async def _write_candidate(self, location: str, document: dict) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.metadata.write.before",
            metadata_location_fingerprint=_fingerprint(location),
            document_fingerprint=_document_fingerprint(document),
            side_effect=True,
        )
        try:
            await self._metadata_store.write(location, document)
        except BaseException:
            await self._compensate(location)
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.open_table_format.metadata.write.after",
            metadata_location_fingerprint=_fingerprint(location),
            document_fingerprint=_document_fingerprint(document),
            side_effect=True,
        )

    async def _compensate(self, location: str) -> None:
        try:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.open_table_format.metadata.compensate.before",
                metadata_location_fingerprint=_fingerprint(location),
                side_effect=True,
            )
            await self._metadata_store.delete(location)
        except BaseException:
            log_event(
                _LOGGER,
                logging.ERROR,
                "glue.open_table_format.metadata.compensate.failed",
                metadata_location_fingerprint=_fingerprint(location),
                fix_hint=(
                    "Inspect the object-store endpoint and remove the unreferenced metadata "
                    "candidate after confirming that no Glue table points to it."
                ),
                exc_info=True,
            )
        else:
            log_event(
                _LOGGER,
                logging.WARNING,
                "glue.open_table_format.metadata.compensate.after",
                metadata_location_fingerprint=_fingerprint(location),
                side_effect=True,
            )

    def _now_ms(self) -> int:
        return int(self._clock.now() * 1000)


def _fingerprint(value: str) -> str:
    return payload_fingerprint(value.encode("utf-8"))


def _document_fingerprint(value: dict) -> str:
    return payload_fingerprint(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
