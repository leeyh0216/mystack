"""Immutable, lossless Glue Data Catalog values and aggregate behavior.

References:
- https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_TableVersion.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_Partition.html
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Self

from mystack.glue.domain.errors import InvalidInputError, VersionMismatchError

DatabaseKey = tuple[str, str]
TableKey = tuple[str, str, str]
PartitionKey = tuple[str, str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class CatalogName:
    value: str

    @classmethod
    def parse(cls, raw: object) -> CatalogName:
        value = str(raw).strip().lower()
        if not value:
            raise InvalidInputError("Catalog names cannot be empty")
        return cls(value)


class CatalogDocument:
    """A defensive, lossless snapshot of an official Glue input document."""

    __slots__ = ("__value",)

    def __init__(self, value: dict[str, Any]) -> None:
        self.__value = copy.deepcopy(value)

    @classmethod
    def named(
        cls,
        value: dict[str, Any],
        *,
        path: str,
    ) -> tuple[CatalogDocument, CatalogName]:
        if "Name" not in value:
            raise InvalidInputError(f"{path} is required")
        name = CatalogName.parse(value["Name"])
        document = copy.deepcopy(value)
        document["Name"] = name.value
        return cls(document), name

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.__value)

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self.__value.get(key, default))

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        del memo
        return self

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CatalogDocument) and self.__value == other.__value

    def __repr__(self) -> str:
        return f"CatalogDocument(keys={sorted(self.__value)})"


@dataclass(frozen=True, slots=True)
class PartitionValues:
    items: tuple[str, ...]

    @classmethod
    def from_items(
        cls,
        values: tuple[str, ...] | list[str],
        *,
        expected_count: int,
    ) -> PartitionValues:
        value = cls(tuple(map(str, values)))
        value.validate_count(expected_count)
        return value

    @classmethod
    def from_document(
        cls,
        document: CatalogDocument,
        *,
        expected_count: int,
    ) -> PartitionValues:
        return cls.from_items(
            document.get("Values", ()),
            expected_count=expected_count,
        )

    def validate_count(self, expected_count: int) -> None:
        if len(self.items) != expected_count:
            raise InvalidInputError(
                f"Partition has {len(self.items)} values but table requires {expected_count}"
            )


@dataclass(frozen=True, slots=True)
class CatalogDatabase:
    catalog_id: str
    _name: CatalogName
    _document: CatalogDocument
    create_time: float

    @classmethod
    def create(cls, catalog_id: str, definition: dict[str, Any], now: float) -> CatalogDatabase:
        document, name = CatalogDocument.named(definition, path="DatabaseInput.Name")
        return cls(catalog_id, name, document, now)

    @classmethod
    def restore(
        cls,
        catalog_id: str,
        name: str,
        definition: dict[str, Any],
        create_time: float,
    ) -> CatalogDatabase:
        return cls(
            catalog_id,
            CatalogName.parse(name),
            CatalogDocument(definition),
            create_time,
        )

    @property
    def name(self) -> str:
        return self._name.value

    @property
    def definition(self) -> dict[str, Any]:
        return self._document.to_dict()

    @staticmethod
    def definition_name(definition: dict[str, Any]) -> str:
        """Validate and normalize a candidate name before repository access."""

        _, value = CatalogDocument.named(definition, path="DatabaseInput.Name")
        return value.value

    def revise(self, definition: dict[str, Any]) -> CatalogDatabase:
        document, name = CatalogDocument.named(definition, path="DatabaseInput.Name")
        return CatalogDatabase(self.catalog_id, name, document, self.create_time)


@dataclass(frozen=True, slots=True)
class CatalogTableVersion:
    version_id: str
    _document: CatalogDocument
    create_time: float
    update_time: float

    @classmethod
    def restore(
        cls,
        version_id: str,
        definition: dict[str, Any],
        create_time: float,
        update_time: float,
    ) -> CatalogTableVersion:
        return cls(version_id, CatalogDocument(definition), create_time, update_time)

    @property
    def definition(self) -> dict[str, Any]:
        return self._document.to_dict()

    @staticmethod
    def validated_id(raw: object) -> str:
        """Validate the documented string representation of an integer version ID."""

        value = str(raw)
        if not value.isascii() or not value.isdigit():
            raise InvalidInputError("Table VersionId must be a string representation of an integer")
        return value


@dataclass(frozen=True, slots=True)
class CatalogTable:
    catalog_id: str
    _database_name: CatalogName
    _name: CatalogName
    _document: CatalogDocument
    create_time: float
    update_time: float
    version_id: str
    archived_versions: tuple[CatalogTableVersion, ...] = ()

    @classmethod
    def create(
        cls,
        catalog_id: str,
        database_name: str,
        definition: dict[str, Any],
        now: float,
    ) -> CatalogTable:
        document, name = CatalogDocument.named(definition, path="TableInput.Name")
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            name,
            document,
            now,
            now,
            "0",
        )

    @classmethod
    def restore(
        cls,
        *,
        catalog_id: str,
        database_name: str,
        name: str,
        definition: dict[str, Any],
        create_time: float,
        update_time: float,
        version_id: str,
        archived_versions: tuple[CatalogTableVersion, ...],
    ) -> CatalogTable:
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            CatalogName.parse(name),
            CatalogDocument(definition),
            create_time,
            update_time,
            version_id,
            archived_versions,
        )

    @property
    def database_name(self) -> str:
        return self._database_name.value

    @property
    def name(self) -> str:
        return self._name.value

    @property
    def definition(self) -> dict[str, Any]:
        return self._document.to_dict()

    @staticmethod
    def definition_name(definition: dict[str, Any]) -> str:
        """Validate and normalize a candidate name before repository access."""

        _, value = CatalogDocument.named(definition, path="TableInput.Name")
        return value.value

    def partition_key_count(self) -> int:
        return len(self._document.get("PartitionKeys", ()))

    def current_version(self) -> CatalogTableVersion:
        return CatalogTableVersion(
            self.version_id,
            self._document,
            self.create_time,
            self.update_time,
        )

    def versions(self) -> tuple[CatalogTableVersion, ...]:
        return (*self.archived_versions, self.current_version())

    def revise(
        self,
        definition: dict[str, Any],
        *,
        now: float,
        expected_version_id: str | None,
        skip_archive: bool,
    ) -> CatalogTable:
        if expected_version_id is not None:
            expected_version_id = CatalogTableVersion.validated_id(expected_version_id)
        if expected_version_id is not None and self.version_id != expected_version_id:
            raise VersionMismatchError(
                f"Expected table version {expected_version_id}, "
                f"current version is {self.version_id}"
            )
        document, name = CatalogDocument.named(definition, path="TableInput.Name")
        archived = self.archived_versions
        if not skip_archive:
            archived = (*archived, self.current_version())
        return CatalogTable(
            self.catalog_id,
            self._database_name,
            name,
            document,
            self.create_time,
            now,
            str(int(self.version_id) + 1),
            archived,
        )

    def move_database(self, database_name: str) -> CatalogTable:
        return CatalogTable(
            self.catalog_id,
            CatalogName.parse(database_name),
            self._name,
            self._document,
            self.create_time,
            self.update_time,
            self.version_id,
            self.archived_versions,
        )


@dataclass(frozen=True, slots=True)
class CatalogPartition:
    catalog_id: str
    _database_name: CatalogName
    _table_name: CatalogName
    _values: PartitionValues
    _document: CatalogDocument
    creation_time: float
    update_time: float

    @classmethod
    def create(
        cls,
        catalog_id: str,
        database_name: str,
        table_name: str,
        definition: dict[str, Any],
        *,
        expected_value_count: int,
        now: float,
    ) -> CatalogPartition:
        document = CatalogDocument(definition)
        values = PartitionValues.from_document(
            document,
            expected_count=expected_value_count,
        )
        normalized = document.to_dict()
        normalized["Values"] = list(values.items)
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            CatalogName.parse(table_name),
            values,
            CatalogDocument(normalized),
            now,
            now,
        )

    @classmethod
    def restore(
        cls,
        *,
        catalog_id: str,
        database_name: str,
        table_name: str,
        values: tuple[str, ...],
        definition: dict[str, Any],
        creation_time: float,
        update_time: float,
    ) -> CatalogPartition:
        return cls(
            catalog_id,
            CatalogName.parse(database_name),
            CatalogName.parse(table_name),
            PartitionValues(tuple(map(str, values))),
            CatalogDocument(definition),
            creation_time,
            update_time,
        )

    @property
    def database_name(self) -> str:
        return self._database_name.value

    @property
    def table_name(self) -> str:
        return self._table_name.value

    @property
    def values(self) -> tuple[str, ...]:
        return self._values.items

    @property
    def definition(self) -> dict[str, Any]:
        return self._document.to_dict()

    def revise(
        self,
        definition: dict[str, Any],
        *,
        expected_value_count: int,
        now: float,
    ) -> CatalogPartition:
        document = CatalogDocument(definition)
        normalized = document.to_dict()
        values = self._values
        if "Values" in normalized:
            values = PartitionValues.from_document(
                document,
                expected_count=expected_value_count,
            )
        else:
            values.validate_count(expected_value_count)
        normalized["Values"] = list(values.items)
        return CatalogPartition(
            self.catalog_id,
            self._database_name,
            self._table_name,
            values,
            CatalogDocument(normalized),
            self.creation_time,
            now,
        )

    def move_database(self, database_name: str) -> CatalogPartition:
        return CatalogPartition(
            self.catalog_id,
            CatalogName.parse(database_name),
            self._table_name,
            self._values,
            self._document,
            self.creation_time,
            self.update_time,
        )

    def move_table(self, table_name: str) -> CatalogPartition:
        return CatalogPartition(
            self.catalog_id,
            self._database_name,
            CatalogName.parse(table_name),
            self._values,
            self._document,
            self.creation_time,
            self.update_time,
        )
