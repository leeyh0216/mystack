"""Apache Iceberg metadata values produced from AWS Glue open-table-format inputs.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateIcebergTableInput.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_IcebergTableUpdate.html
- https://iceberg.apache.org/spec/#table-metadata
- https://iceberg.apache.org/spec/#schemas
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from mystack.glue.domain.errors import InvalidInputError

_DECIMAL = re.compile(r"decimal\((\d+),(\d+)\)")
_FIXED = re.compile(r"fixed\[(\d+)\]")
_PARAMETERIZED_TRANSFORM = re.compile(r"(bucket|truncate)\[(\d+)\]")
_PRIMITIVES = frozenset(
    {
        "boolean",
        "int",
        "long",
        "float",
        "double",
        "date",
        "time",
        "timestamp",
        "timestamptz",
        "string",
        "uuid",
        "binary",
    }
)
_SIMPLE_TRANSFORMS = frozenset({"identity", "year", "month", "day", "hour", "void"})
_MAX_SCHEMA_FIELD_ID = 2_147_483_447


@dataclass(frozen=True, slots=True)
class PlannedIcebergTable:
    metadata_location: str
    metadata: dict[str, Any]
    table_definition: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IcebergSchemaDefinition:
    document: dict[str, Any]
    field_types: dict[int, Any]
    required_field_ids: frozenset[int]
    identifier_eligible_field_ids: frozenset[int]

    @classmethod
    def parse(cls, raw: object) -> IcebergSchemaDefinition:
        value = _mapping(raw, "Schema")
        schema_id = _integer(value.get("SchemaId", 0), "Schema.SchemaId", minimum=0)
        if value.get("Type", "struct") != "struct":
            raise InvalidInputError("Schema.Type must be 'struct'")
        fields = _list(value.get("Fields"), "Schema.Fields")
        normalized: list[dict[str, Any]] = []
        field_types: dict[int, Any] = {}
        required_ids: set[int] = set()
        identifier_eligible_ids: set[int] = set()
        _normalize_fields(
            fields,
            path="Schema.Fields",
            normalized=normalized,
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=True,
        )
        identifiers = [
            _integer(item, "Schema.IdentifierFieldIds", minimum=1)
            for item in _list(value.get("IdentifierFieldIds", []), "Schema.IdentifierFieldIds")
        ]
        if len(identifiers) != len(set(identifiers)):
            raise InvalidInputError("Schema.IdentifierFieldIds must be unique")
        for field_id in identifiers:
            if field_id not in field_types:
                raise InvalidInputError(
                    f"Schema identifier field ID {field_id} does not exist in Fields"
                )
            if field_id not in identifier_eligible_ids:
                raise InvalidInputError(
                    f"Schema identifier field ID {field_id} must identify a required primitive "
                    "field outside optional, list, and map paths"
                )
        document: dict[str, Any] = {
            "type": "struct",
            "schema-id": schema_id,
            "fields": normalized,
        }
        if identifiers:
            document["identifier-field-ids"] = identifiers
        return cls(
            document,
            field_types,
            frozenset(required_ids),
            frozenset(identifier_eligible_ids),
        )

    @property
    def schema_id(self) -> int:
        return int(self.document["schema-id"])

    @property
    def last_column_id(self) -> int:
        return max(self.field_types, default=0)

    def glue_columns(self) -> list[dict[str, str]]:
        return [
            {
                "Name": str(field["name"]),
                "Type": _glue_type(field["type"]),
                **({"Comment": str(field["doc"])} if "doc" in field else {}),
            }
            for field in self.document["fields"]
        ]


@dataclass(frozen=True, slots=True)
class IcebergPartitionSpecDefinition:
    document: dict[str, Any]
    last_partition_id: int

    @classmethod
    def parse(
        cls,
        raw: object | None,
        schema: IcebergSchemaDefinition,
    ) -> IcebergPartitionSpecDefinition:
        if raw is None:
            return cls({"spec-id": 0, "fields": []}, 999)
        value = _mapping(raw, "PartitionSpec")
        spec_id = _integer(value.get("SpecId", 0), "PartitionSpec.SpecId", minimum=0)
        fields = _list(value.get("Fields"), "PartitionSpec.Fields")
        normalized: list[dict[str, Any]] = []
        names: set[str] = set()
        field_ids: set[int] = set()
        next_field_id = 1000
        for index, raw_field in enumerate(fields):
            path = f"PartitionSpec.Fields[{index}]"
            field = _mapping(raw_field, path)
            source_id = _integer(field.get("SourceId"), f"{path}.SourceId", minimum=1)
            if source_id not in schema.field_types:
                raise InvalidInputError(f"{path}.SourceId {source_id} does not exist in Schema")
            name = _non_empty_string(field.get("Name"), f"{path}.Name")
            if name in names:
                raise InvalidInputError("PartitionSpec field names must be unique")
            names.add(name)
            transform = _transform(field.get("Transform"), f"{path}.Transform")
            _validate_transform(
                transform,
                schema.field_types[source_id],
                f"{path}.Transform",
            )
            while next_field_id in field_ids:
                next_field_id += 1
            field_id = _integer(
                field.get("FieldId", next_field_id),
                f"{path}.FieldId",
                minimum=1000,
            )
            if field_id in field_ids:
                raise InvalidInputError("PartitionSpec field IDs must be unique")
            field_ids.add(field_id)
            next_field_id = max(next_field_id, field_id + 1)
            normalized.append(
                {
                    "source-id": source_id,
                    "field-id": field_id,
                    "name": name,
                    "transform": transform,
                }
            )
        return cls(
            {"spec-id": spec_id, "fields": normalized},
            max(field_ids, default=999),
        )

    @property
    def spec_id(self) -> int:
        return int(self.document["spec-id"])


@dataclass(frozen=True, slots=True)
class IcebergSortOrderDefinition:
    document: dict[str, Any]

    @classmethod
    def parse(
        cls,
        raw: object | None,
        schema: IcebergSchemaDefinition,
    ) -> IcebergSortOrderDefinition:
        if raw is None:
            return cls({"order-id": 0, "fields": []})
        value = _mapping(raw, "SortOrder")
        order_id = _integer(value.get("OrderId"), "SortOrder.OrderId", minimum=0)
        fields = _list(value.get("Fields"), "SortOrder.Fields")
        if fields and order_id == 0:
            raise InvalidInputError("SortOrder.OrderId 0 is reserved for an unsorted table")
        normalized: list[dict[str, Any]] = []
        for index, raw_field in enumerate(fields):
            path = f"SortOrder.Fields[{index}]"
            field = _mapping(raw_field, path)
            source_id = _integer(field.get("SourceId"), f"{path}.SourceId", minimum=1)
            if source_id not in schema.field_types:
                raise InvalidInputError(f"{path}.SourceId {source_id} does not exist in Schema")
            direction = str(field.get("Direction", ""))
            if direction not in {"asc", "desc"}:
                raise InvalidInputError(f"{path}.Direction must be 'asc' or 'desc'")
            null_order = str(field.get("NullOrder", ""))
            if null_order not in {"nulls-first", "nulls-last"}:
                raise InvalidInputError(f"{path}.NullOrder must be 'nulls-first' or 'nulls-last'")
            normalized.append(
                {
                    "source-id": source_id,
                    "transform": _validated_transform(
                        field.get("Transform"),
                        schema.field_types[source_id],
                        f"{path}.Transform",
                    ),
                    "direction": direction,
                    "null-order": null_order,
                }
            )
        return cls({"order-id": order_id, "fields": normalized})

    @property
    def order_id(self) -> int:
        return int(self.document["order-id"])


class IcebergOpenTableFormatPlanner:
    """Validate Glue inputs and produce complete Iceberg v2 metadata transitions."""

    def create(
        self,
        *,
        table_name: object,
        iceberg_input: object,
        now_ms: int,
        identifier: str,
    ) -> PlannedIcebergTable:
        value = _mapping(iceberg_input, "OpenTableFormatInput.IcebergInput")
        if value.get("MetadataOperation") != "CREATE":
            raise InvalidInputError("IcebergInput.MetadataOperation must be CREATE")
        version = str(value.get("Version", "2"))
        if version != "2":
            raise InvalidInputError("Mystack Glue 5.0 open-table profile supports Iceberg v2")
        create_input = _mapping(
            value.get("CreateIcebergTableInput"),
            "IcebergInput.CreateIcebergTableInput",
        )
        name = _non_empty_string(table_name, "Name").lower()
        location = _s3_location(create_input.get("Location"), "CreateIcebergTableInput.Location")
        schema = IcebergSchemaDefinition.parse(create_input.get("Schema"))
        partition = IcebergPartitionSpecDefinition.parse(create_input.get("PartitionSpec"), schema)
        sort_order = IcebergSortOrderDefinition.parse(create_input.get("WriteOrder"), schema)
        properties = _string_map(create_input.get("Properties", {}), "Properties")
        metadata_location = _metadata_location(location, 0, identifier)
        metadata = {
            "format-version": 2,
            "table-uuid": identifier,
            "location": location,
            "last-sequence-number": 0,
            "last-updated-ms": now_ms,
            "last-column-id": schema.last_column_id,
            "schemas": [copy.deepcopy(schema.document)],
            "current-schema-id": schema.schema_id,
            "partition-specs": [copy.deepcopy(partition.document)],
            "default-spec-id": partition.spec_id,
            "last-partition-id": partition.last_partition_id,
            "properties": properties,
            "current-snapshot-id": -1,
            "snapshots": [],
            "snapshot-log": [],
            "metadata-log": [],
            "sort-orders": [copy.deepcopy(sort_order.document)],
            "default-sort-order-id": sort_order.order_id,
            "refs": {},
        }
        return PlannedIcebergTable(
            metadata_location,
            metadata,
            _table_definition(name, metadata_location, metadata, schema),
        )

    def update(
        self,
        *,
        table_definition: dict[str, Any],
        current_metadata_location: str,
        current_metadata: dict[str, Any],
        update_input: object,
        now_ms: int,
        identifier: str,
    ) -> PlannedIcebergTable:
        value = _mapping(update_input, "UpdateOpenTableFormatInput.UpdateIcebergInput")
        table_input = _mapping(
            value.get("UpdateIcebergTableInput"),
            "UpdateIcebergInput.UpdateIcebergTableInput",
        )
        updates = _list(table_input.get("Updates"), "UpdateIcebergTableInput.Updates")
        if not updates:
            raise InvalidInputError("UpdateIcebergTableInput.Updates cannot be empty")
        metadata = copy.deepcopy(current_metadata)
        if int(metadata.get("format-version", 0)) != 2:
            raise InvalidInputError("Mystack Glue 5.0 open-table profile supports Iceberg v2")
        for index, raw_update in enumerate(updates):
            self._apply_update(metadata, raw_update, index)
        previous_updated = int(current_metadata.get("last-updated-ms", now_ms))
        metadata["last-updated-ms"] = now_ms
        metadata_log = list(metadata.get("metadata-log", []))
        metadata_log.append(
            {"timestamp-ms": previous_updated, "metadata-file": current_metadata_location}
        )
        metadata["metadata-log"] = metadata_log
        metadata_version = _next_metadata_version(current_metadata_location, metadata_log)
        metadata_location = _metadata_location(
            _s3_location(metadata.get("location"), "Iceberg metadata location"),
            metadata_version,
            identifier,
        )
        current_schema = _current_schema(metadata)
        definition = copy.deepcopy(table_definition)
        definition["TableType"] = "EXTERNAL_TABLE"
        definition["StorageDescriptor"] = {
            **dict(definition.get("StorageDescriptor", {})),
            "Columns": IcebergSchemaDefinition.parse(_api_schema(current_schema)).glue_columns(),
            "Location": str(metadata["location"]),
        }
        parameters = dict(definition.get("Parameters", {}))
        parameters.update(
            {
                "table_type": "ICEBERG",
                "format-version": "2",
                "previous_metadata_location": current_metadata_location,
                "metadata_location": metadata_location,
            }
        )
        definition["Parameters"] = parameters
        definition["PartitionKeys"] = []
        return PlannedIcebergTable(metadata_location, metadata, definition)

    def _apply_update(
        self,
        metadata: dict[str, Any],
        raw_update: object,
        index: int,
    ) -> None:
        path = f"UpdateIcebergTableInput.Updates[{index}]"
        update = _mapping(raw_update, path)
        schema = IcebergSchemaDefinition.parse(update.get("Schema"))
        location = _s3_location(update.get("Location"), f"{path}.Location")
        action = update.get("Action")
        action_name = str(action) if action is not None else None
        if action_name in {"add-encryption-key", "remove-encryption-key"}:
            raise InvalidInputError(
                "Iceberg encryption-key updates are outside the Glue 5.0 runtime profile"
            )

        if action_name is None:
            _upsert(metadata, "schemas", "schema-id", schema.document)
            metadata["current-schema-id"] = schema.schema_id
            metadata["last-column-id"] = max(
                int(metadata.get("last-column-id", 0)), schema.last_column_id
            )
            if "PartitionSpec" in update:
                partition = IcebergPartitionSpecDefinition.parse(update["PartitionSpec"], schema)
                _upsert(metadata, "partition-specs", "spec-id", partition.document)
                metadata["default-spec-id"] = partition.spec_id
                metadata["last-partition-id"] = max(
                    int(metadata.get("last-partition-id", 999)),
                    partition.last_partition_id,
                )
            if "SortOrder" in update:
                sort_order = IcebergSortOrderDefinition.parse(update["SortOrder"], schema)
                _upsert(metadata, "sort-orders", "order-id", sort_order.document)
                metadata["default-sort-order-id"] = sort_order.order_id
            metadata["location"] = location
            metadata.setdefault("properties", {}).update(
                _string_map(update.get("Properties", {}), f"{path}.Properties")
            )
            return

        if action_name == "add-schema":
            _add_unique(metadata, "schemas", "schema-id", schema.document)
            metadata["last-column-id"] = max(
                int(metadata.get("last-column-id", 0)), schema.last_column_id
            )
        elif action_name == "set-current-schema":
            _require_existing(metadata, "schemas", "schema-id", schema.document)
            metadata["current-schema-id"] = schema.schema_id
        elif action_name in {"add-spec", "set-default-spec"}:
            partition = IcebergPartitionSpecDefinition.parse(update.get("PartitionSpec"), schema)
            if "PartitionSpec" not in update:
                raise InvalidInputError(f"{path}.PartitionSpec is required for {action_name}")
            if action_name == "add-spec":
                _add_unique(metadata, "partition-specs", "spec-id", partition.document)
            else:
                _require_existing(metadata, "partition-specs", "spec-id", partition.document)
                metadata["default-spec-id"] = partition.spec_id
            metadata["last-partition-id"] = max(
                int(metadata.get("last-partition-id", 999)), partition.last_partition_id
            )
        elif action_name in {"add-sort-order", "set-default-sort-order"}:
            if "SortOrder" not in update:
                raise InvalidInputError(f"{path}.SortOrder is required for {action_name}")
            sort_order = IcebergSortOrderDefinition.parse(update["SortOrder"], schema)
            if action_name == "add-sort-order":
                _add_unique(metadata, "sort-orders", "order-id", sort_order.document)
            else:
                _require_existing(metadata, "sort-orders", "order-id", sort_order.document)
                metadata["default-sort-order-id"] = sort_order.order_id
        elif action_name == "set-location":
            metadata["location"] = location
        elif action_name == "set-properties":
            metadata.setdefault("properties", {}).update(
                _string_map(update.get("Properties", {}), f"{path}.Properties")
            )
        elif action_name == "remove-properties":
            properties = metadata.setdefault("properties", {})
            for name in _string_map(update.get("Properties", {}), f"{path}.Properties"):
                properties.pop(name, None)
        else:
            raise InvalidInputError(f"Unsupported Iceberg update action {action_name!r}")


def _normalize_fields(
    fields: list[Any],
    *,
    path: str,
    normalized: list[dict[str, Any]],
    field_types: dict[int, Any],
    required_ids: set[int],
    identifier_eligible_ids: set[int],
    identifier_path_allowed: bool,
) -> None:
    names: set[str] = set()
    for index, raw_field in enumerate(fields):
        field_path = f"{path}[{index}]"
        field = _mapping(raw_field, field_path)
        field_id = _integer(
            _member(field, "Id", "id"),
            f"{field_path}.Id",
            minimum=1,
            maximum=_MAX_SCHEMA_FIELD_ID,
        )
        if field_id in field_types:
            raise InvalidInputError(f"Iceberg field ID {field_id} must be globally unique")
        name = _non_empty_string(_member(field, "Name", "name"), f"{field_path}.Name")
        if name in names:
            raise InvalidInputError(f"Field names in {path} must be unique")
        names.add(name)
        required = _boolean(_member(field, "Required", "required"), f"{field_path}.Required")
        raw_type = _member(field, "Type", "type")
        # Reserve the parent before descending so a nested field cannot reuse its ID.
        field_types[field_id] = _MISSING
        normalized_type = _normalize_type(
            raw_type,
            path=f"{field_path}.Type",
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=identifier_path_allowed and required,
        )
        field_types[field_id] = normalized_type
        if required:
            required_ids.add(field_id)
            if (
                identifier_path_allowed
                and not isinstance(normalized_type, dict)
                and normalized_type not in {"float", "double"}
            ):
                identifier_eligible_ids.add(field_id)
        value: dict[str, Any] = {
            "id": field_id,
            "name": name,
            "required": required,
            "type": normalized_type,
        }
        for source, target in (
            ("Doc", "doc"),
            ("InitialDefault", "initial-default"),
            ("WriteDefault", "write-default"),
        ):
            raw_value = _member(field, source, target, default=_MISSING)
            if raw_value is not _MISSING:
                value[target] = copy.deepcopy(raw_value)
        normalized.append(value)


def _normalize_type(
    raw: object,
    *,
    path: str,
    field_types: dict[int, Any],
    required_ids: set[int],
    identifier_eligible_ids: set[int],
    identifier_path_allowed: bool,
) -> Any:
    if isinstance(raw, str):
        if raw in _PRIMITIVES:
            return raw
        decimal = _DECIMAL.fullmatch(raw)
        if (
            decimal
            and 1 <= int(decimal.group(1)) <= 38
            and 0 <= int(decimal.group(2)) <= int(decimal.group(1))
        ):
            return raw
        fixed = _FIXED.fullmatch(raw)
        if fixed and int(fixed.group(1)) > 0:
            return raw
        raise InvalidInputError(f"{path} has unsupported Iceberg primitive {raw!r}")
    value = _mapping(raw, path)
    type_name = str(value.get("type", ""))
    if type_name == "struct":
        normalized: list[dict[str, Any]] = []
        _normalize_fields(
            _list(value.get("fields"), f"{path}.fields"),
            path=f"{path}.fields",
            normalized=normalized,
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=identifier_path_allowed,
        )
        return {"type": "struct", "fields": normalized}
    if type_name == "list":
        element_id = _integer(
            value.get("element-id"),
            f"{path}.element-id",
            minimum=1,
            maximum=_MAX_SCHEMA_FIELD_ID,
        )
        if element_id in field_types:
            raise InvalidInputError(f"Iceberg field ID {element_id} must be globally unique")
        field_types[element_id] = _MISSING
        element_required = _boolean(value.get("element-required"), f"{path}.element-required")
        element = _normalize_type(
            value.get("element"),
            path=f"{path}.element",
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=False,
        )
        field_types[element_id] = element
        if element_required:
            required_ids.add(element_id)
        return {
            "type": "list",
            "element-id": element_id,
            "element": element,
            "element-required": element_required,
        }
    if type_name == "map":
        key_id = _integer(
            value.get("key-id"),
            f"{path}.key-id",
            minimum=1,
            maximum=_MAX_SCHEMA_FIELD_ID,
        )
        value_id = _integer(
            value.get("value-id"),
            f"{path}.value-id",
            minimum=1,
            maximum=_MAX_SCHEMA_FIELD_ID,
        )
        if key_id == value_id or key_id in field_types or value_id in field_types:
            raise InvalidInputError("Iceberg map key/value field IDs must be globally unique")
        field_types[key_id] = _MISSING
        field_types[value_id] = _MISSING
        key_type = _normalize_type(
            value.get("key"),
            path=f"{path}.key",
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=False,
        )
        value_required = _boolean(value.get("value-required"), f"{path}.value-required")
        value_type = _normalize_type(
            value.get("value"),
            path=f"{path}.value",
            field_types=field_types,
            required_ids=required_ids,
            identifier_eligible_ids=identifier_eligible_ids,
            identifier_path_allowed=False,
        )
        field_types[key_id] = key_type
        field_types[value_id] = value_type
        required_ids.add(key_id)
        if value_required:
            required_ids.add(value_id)
        return {
            "type": "map",
            "key-id": key_id,
            "key": key_type,
            "value-id": value_id,
            "value": value_type,
            "value-required": value_required,
        }
    raise InvalidInputError(f"{path} must be a primitive, struct, list, or map")


def _glue_type(value: Any) -> str:
    if isinstance(value, str):
        return {
            "long": "bigint",
            "time": "string",
            "timestamptz": "timestamp",
            "uuid": "string",
        }.get(value, "binary" if _FIXED.fullmatch(value) else value)
    type_name = value["type"]
    if type_name == "struct":
        return (
            "struct<"
            + ",".join(f"{field['name']}:{_glue_type(field['type'])}" for field in value["fields"])
            + ">"
        )
    if type_name == "list":
        return f"array<{_glue_type(value['element'])}>"
    if type_name == "map":
        return f"map<{_glue_type(value['key'])},{_glue_type(value['value'])}>"
    raise InvalidInputError(f"Unsupported normalized Iceberg type {type_name!r}")


def _table_definition(
    name: str,
    metadata_location: str,
    metadata: dict[str, Any],
    schema: IcebergSchemaDefinition,
) -> dict[str, Any]:
    return {
        "Name": name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "format-version": str(metadata["format-version"]),
            "metadata_location": metadata_location,
        },
        "PartitionKeys": [],
        "StorageDescriptor": {
            "Columns": schema.glue_columns(),
            "Location": str(metadata["location"]),
        },
    }


def _current_schema(metadata: dict[str, Any]) -> dict[str, Any]:
    current_id = metadata.get("current-schema-id")
    for schema in metadata.get("schemas", []):
        if schema.get("schema-id") == current_id:
            return dict(schema)
    raise InvalidInputError("Iceberg metadata current-schema-id does not identify a schema")


def _api_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "SchemaId": schema["schema-id"],
        "Type": schema.get("type", "struct"),
        "IdentifierFieldIds": schema.get("identifier-field-ids", []),
        "Fields": [_api_field(field) for field in schema["fields"]],
    }


def _api_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "Id": field["id"],
        "Name": field["name"],
        "Required": field["required"],
        "Type": field["type"],
        **({"Doc": field["doc"]} if "doc" in field else {}),
        **({"InitialDefault": field["initial-default"]} if "initial-default" in field else {}),
        **({"WriteDefault": field["write-default"]} if "write-default" in field else {}),
    }


def _upsert(metadata: dict[str, Any], collection: str, key: str, value: dict[str, Any]) -> None:
    items = list(metadata.get(collection, []))
    for index, current in enumerate(items):
        if current.get(key) == value[key]:
            items[index] = copy.deepcopy(value)
            metadata[collection] = items
            return
    items.append(copy.deepcopy(value))
    metadata[collection] = items


def _add_unique(metadata: dict[str, Any], collection: str, key: str, value: dict[str, Any]) -> None:
    for current in metadata.get(collection, []):
        if current.get(key) == value[key]:
            raise InvalidInputError(f"Iceberg {collection} ID {value[key]} already exists")
    metadata.setdefault(collection, []).append(copy.deepcopy(value))


def _require_existing(
    metadata: dict[str, Any], collection: str, key: str, value: dict[str, Any]
) -> None:
    for current in metadata.get(collection, []):
        if current.get(key) == value[key]:
            if current != value:
                raise InvalidInputError(
                    f"Iceberg {collection} ID {value[key]} does not match its existing definition"
                )
            return
    raise InvalidInputError(f"Iceberg {collection} ID {value[key]} does not exist")


def _metadata_location(location: str, version: int, identifier: str) -> str:
    return f"{location.rstrip('/')}/metadata/{version:05d}-{identifier}.metadata.json"


def _next_metadata_version(location: str, metadata_log: list[Any]) -> int:
    name = location.rsplit("/", maxsplit=1)[-1]
    match = re.match(r"(\d+)-", name)
    return int(match.group(1)) + 1 if match else len(metadata_log)


def _s3_location(value: object, path: str) -> str:
    location = _non_empty_string(value, path).rstrip("/")
    parsed = urlparse(location)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise InvalidInputError(f"{path} must be an absolute s3://bucket/key location")
    if parsed.params or parsed.query or parsed.fragment:
        raise InvalidInputError(f"{path} cannot contain parameters, a query, or a fragment")
    return location


def _transform(value: object, path: str) -> str:
    transform = _non_empty_string(value, path).lower()
    if transform in _SIMPLE_TRANSFORMS:
        return transform
    match = _PARAMETERIZED_TRANSFORM.fullmatch(transform)
    if match and int(match.group(2)) > 0:
        return transform
    raise InvalidInputError(f"{path} has unsupported transform {transform!r}")


def _validated_transform(value: object, source_type: Any, path: str) -> str:
    transform = _transform(value, path)
    _validate_transform(transform, source_type, path)
    return transform


def _validate_transform(transform: str, source_type: Any, path: str) -> None:
    if isinstance(source_type, dict):
        raise InvalidInputError(f"{path} requires a primitive source field")
    family = _type_family(source_type)
    if transform in {"identity", "void"}:
        return
    if transform in {"year", "month", "day"}:
        allowed = {"date", "timestamp", "timestamptz"}
    elif transform == "hour":
        allowed = {"timestamp", "timestamptz"}
    elif transform.startswith("bucket["):
        allowed = {
            "int",
            "long",
            "decimal",
            "date",
            "time",
            "timestamp",
            "timestamptz",
            "string",
            "uuid",
            "fixed",
            "binary",
        }
    else:
        allowed = {"int", "long", "decimal", "string", "binary"}
    if family not in allowed:
        raise InvalidInputError(
            f"{path} transform {transform!r} is not valid for Iceberg type {source_type!r}"
        )


def _type_family(value: str) -> str:
    if _DECIMAL.fullmatch(value):
        return "decimal"
    if _FIXED.fullmatch(value):
        return "fixed"
    return value


def _string_map(value: object, path: str) -> dict[str, str]:
    raw = _mapping(value, path)
    result = {str(key): str(item) for key, item in raw.items()}
    if any(not key for key in result):
        raise InvalidInputError(f"{path} keys cannot be empty")
    return result


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidInputError(f"{path} is required and must be a structure")
    return dict(value)


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise InvalidInputError(f"{path} is required and must be a list")
    return list(value)


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{path} is required and cannot be empty")
    return value.strip()


def _integer(
    value: object,
    path: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        maximum_message = f" and no greater than {maximum}" if maximum is not None else ""
        raise InvalidInputError(
            f"{path} must be an integer greater than or equal to {minimum}{maximum_message}"
        )
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidInputError(f"{path} must be a boolean")
    return value


_MISSING = object()


def _member(
    value: dict[str, Any],
    primary: str,
    alternate: str,
    *,
    default: object = _MISSING,
) -> object:
    if primary in value:
        return value[primary]
    if alternate in value:
        return value[alternate]
    return default
