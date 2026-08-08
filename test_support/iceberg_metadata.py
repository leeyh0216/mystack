"""Read-only assertions over Iceberg table metadata written by the real client.

References:
- https://iceberg.apache.org/spec/#table-metadata
- https://iceberg.apache.org/spec/#partition-transforms
- https://iceberg.apache.org/spec/#sorting-and-sort-orders
- https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class IcebergMetadataDocument:
    """Expose semantic metadata assertions without coupling tests to JSON list positions."""

    document: dict[str, Any]

    @classmethod
    def load_from_s3(cls, s3: Any, metadata_location: str) -> IcebergMetadataDocument:
        location = urlsplit(metadata_location)
        if location.scheme != "s3" or not location.netloc or not location.path.lstrip("/"):
            raise ValueError("Iceberg metadata_location must be a non-empty s3 URI")
        response = s3.get_object(Bucket=location.netloc, Key=location.path.lstrip("/"))
        body = response["Body"]
        try:
            document = json.loads(body.read())
        finally:
            body.close()
        if not isinstance(document, dict):
            raise ValueError("Iceberg table metadata must be a JSON object")
        return cls(document)

    def current_schema(self) -> dict[str, Any]:
        schema_id = self.document["current-schema-id"]
        return self._by_id("schemas", "schema-id", schema_id)

    def top_level_field_names(self) -> list[str]:
        return [str(field["name"]) for field in self.current_schema()["fields"]]

    def field_type(self, dotted_name: str) -> Any:
        return self._field(dotted_name)["type"]

    def has_field(self, dotted_name: str) -> bool:
        try:
            self._field(dotted_name)
        except KeyError:
            return False
        return True

    def identifier_field_names(self) -> set[str]:
        schema = self.current_schema()
        return {
            self._field_name_by_id(int(field_id))
            for field_id in schema.get("identifier-field-ids", ())
        }

    def all_partition_transforms(self) -> set[str]:
        return {
            str(field["transform"])
            for spec in self.document["partition-specs"]
            for field in spec["fields"]
        }

    def current_partition_transforms(self) -> set[str]:
        spec = self._by_id(
            "partition-specs",
            "spec-id",
            self.document["default-spec-id"],
        )
        return {str(field["transform"]) for field in spec["fields"]}

    def current_sort_fields(self) -> list[dict[str, Any]]:
        order = self._by_id(
            "sort-orders",
            "order-id",
            self.document["default-sort-order-id"],
        )
        return [
            {
                "source_name": self._field_name_by_id(int(field["source-id"])),
                "transform": field["transform"],
                "direction": field["direction"],
                "null_order": field["null-order"],
            }
            for field in order["fields"]
        ]

    def _field(self, dotted_name: str) -> dict[str, Any]:
        fields = self.current_schema()["fields"]
        field: dict[str, Any] | None = None
        for part in dotted_name.split("."):
            field = next((value for value in fields if value["name"] == part), None)
            if field is None:
                raise KeyError(dotted_name)
            field_type = field["type"]
            fields = (
                field_type.get("fields", ())
                if isinstance(field_type, dict) and field_type.get("type") == "struct"
                else ()
            )
        assert field is not None
        return field

    def _field_name_by_id(self, expected_id: int) -> str:
        def visit(fields: list[dict[str, Any]], prefix: str = "") -> str | None:
            for field in fields:
                name = f"{prefix}.{field['name']}" if prefix else str(field["name"])
                if int(field["id"]) == expected_id:
                    return name
                field_type = field["type"]
                if isinstance(field_type, dict) and field_type.get("type") == "struct":
                    nested = visit(field_type["fields"], name)
                    if nested is not None:
                        return nested
            return None

        found = visit(self.current_schema()["fields"])
        if found is None:
            raise KeyError(f"Unknown current Iceberg field ID {expected_id}")
        return found

    def _by_id(self, collection: str, member: str, expected: int) -> dict[str, Any]:
        try:
            return next(
                value for value in self.document[collection] if int(value[member]) == int(expected)
            )
        except StopIteration as error:
            raise KeyError(f"Missing Iceberg {collection} entry {member}={expected}") from error
