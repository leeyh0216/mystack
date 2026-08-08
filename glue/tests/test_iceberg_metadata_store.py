"""S3 Iceberg metadata adapter serialization and failure boundaries.

References:
- https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object.html
- https://iceberg.apache.org/spec/#table-metadata
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

import pytest
from mystack.glue.adapters.outbound.iceberg_metadata import S3IcebergMetadataStore


@dataclass(frozen=True)
class Settings:
    endpoint_url: str = "http://object-store.invalid"
    region: str = "us-east-1"
    access_key_id: str = "test"
    secret_access_key: str = "test"
    s3_path_style: bool = True


class MemoryS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.closed = False

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = bytes(kwargs["Body"])
        return {}

    def delete_object(self, **kwargs):
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)
        return {}

    def close(self) -> None:
        self.closed = True


async def test_metadata_store_round_trip_is_deterministic_and_delete_is_idempotent() -> None:
    client = MemoryS3Client()
    store = S3IcebergMetadataStore(Settings(), client=client)
    location = "s3://warehouse/table/metadata/00000-id.metadata.json"

    await store.write(location, {"z": 1, "a": {"value": 2}})

    assert client.objects[("warehouse", "table/metadata/00000-id.metadata.json")] == (
        b'{"a":{"value":2},"z":1}'
    )
    assert await store.read(location) == {"a": {"value": 2}, "z": 1}
    await store.delete(location)
    await store.delete(location)
    await store.close()
    assert client.closed is True


async def test_metadata_store_maps_invalid_json_to_storage_failure() -> None:
    client = MemoryS3Client()
    client.objects[("warehouse", "metadata.json")] = b"not-json"
    store = S3IcebergMetadataStore(Settings(), client=client)

    with pytest.raises(OSError, match="read the current"):
        await store.read("s3://warehouse/metadata.json")


async def test_metadata_store_writes_valid_json_document() -> None:
    client = MemoryS3Client()
    store = S3IcebergMetadataStore(Settings(), client=client)

    await store.write("s3://warehouse/metadata.json", {"format-version": 2})

    assert json.loads(client.objects[("warehouse", "metadata.json")]) == {"format-version": 2}
