"""LocalStack-compatible S3 adapter for Apache Iceberg metadata JSON.

Official references:
- https://iceberg.apache.org/spec/#table-metadata
- https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from mystack.aws_protocol.observability import log_event, payload_fingerprint

_LOGGER = logging.getLogger(__name__)


class ObjectStoreConfiguration(Protocol):
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    s3_path_style: bool


class S3ObjectClient(Protocol):
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def delete_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def close(self) -> None: ...


class S3IcebergMetadataStore:
    """Read and write metadata objects; catalog pointer publication stays in the application."""

    def __init__(
        self,
        settings: ObjectStoreConfiguration,
        *,
        client: S3ObjectClient | None = None,
    ) -> None:
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            config=Config(s3={"addressing_style": "path" if settings.s3_path_style else "auto"}),
        )
        self._closed = False

    async def read(self, location: str) -> dict[str, Any]:
        bucket, key = self._address("read", location)
        self._require_open()
        self._log_boundary("read", "before", bucket, key)
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=bucket,
                Key=key,
            )
            body = response["Body"]
            try:
                raw = await asyncio.to_thread(body.read)
            finally:
                await asyncio.to_thread(body.close)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("Iceberg metadata root must be an object")
        except Exception as error:
            self._log_failure("read", bucket, key, error)
            raise OSError("Unable to read the current Iceberg metadata document") from error
        self._log_boundary("read", "after", bucket, key, size_bytes=len(raw))
        return value

    async def write(self, location: str, document: dict[str, Any]) -> None:
        bucket, key = self._address("write", location)
        self._require_open()
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        self._log_boundary("write", "before", bucket, key, size_bytes=len(payload))
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
            )
        except Exception as error:
            self._log_failure("write", bucket, key, error)
            raise OSError("Unable to write an Iceberg metadata candidate") from error
        self._log_boundary("write", "after", bucket, key, size_bytes=len(payload))

    async def delete(self, location: str) -> None:
        bucket, key = self._address("delete", location)
        self._require_open()
        self._log_boundary("delete", "before", bucket, key)
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=bucket,
                Key=key,
            )
        except Exception as error:
            self._log_failure("delete", bucket, key, error)
            raise OSError("Unable to delete an unreferenced Iceberg metadata candidate") from error
        self._log_boundary("delete", "after", bucket, key)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.iceberg_metadata_store.close.before",
            side_effect=True,
        )
        await asyncio.to_thread(self._client.close)
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.iceberg_metadata_store.close.after",
            side_effect=True,
        )

    def _require_open(self) -> None:
        if self._closed:
            raise OSError("Glue Iceberg metadata store is closed")

    @staticmethod
    def _address(operation: str, location: str) -> tuple[str, str]:
        try:
            return _object_address(location)
        except OSError:
            log_event(
                _LOGGER,
                logging.ERROR,
                f"glue.iceberg_metadata.{operation}.address_invalid",
                metadata_location_fingerprint=payload_fingerprint(location.encode("utf-8")),
                fix_hint=(
                    "Inspect the Glue table metadata_location producer and require an absolute "
                    "s3://bucket/key URI without URI parameters."
                ),
                side_effect=False,
                exc_info=True,
            )
            raise

    @staticmethod
    def _log_boundary(
        operation: str,
        phase: str,
        bucket: str,
        key: str,
        *,
        size_bytes: int | None = None,
    ) -> None:
        log_event(
            _LOGGER,
            logging.INFO,
            f"glue.iceberg_metadata.{operation}.{phase}",
            bucket=bucket,
            key_fingerprint=payload_fingerprint(key.encode("utf-8")),
            size_bytes=size_bytes,
            side_effect=True,
        )

    @staticmethod
    def _log_failure(operation: str, bucket: str, key: str, error: Exception) -> None:
        log_event(
            _LOGGER,
            logging.ERROR,
            f"glue.iceberg_metadata.{operation}.failed",
            bucket=bucket,
            key_fingerprint=payload_fingerprint(key.encode("utf-8")),
            failure_type=type(error).__name__,
            fix_hint=(
                "Verify localstack.endpoint_url, credentials, S3 addressing style, bucket "
                "existence, and the Iceberg metadata pointer codec."
            ),
            side_effect=True,
            exc_info=True,
        )


def _object_address(location: str) -> tuple[str, str]:
    parsed = urlparse(location)
    key = parsed.path.lstrip("/")
    if parsed.scheme != "s3" or not parsed.netloc or not key:
        raise OSError("Iceberg metadata location must be an absolute s3://bucket/key URI")
    if parsed.params or parsed.query or parsed.fragment:
        raise OSError("Iceberg metadata location cannot contain URI parameters")
    return parsed.netloc, key
