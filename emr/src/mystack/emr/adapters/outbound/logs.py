"""Publish local EMR Step and Spark driver logs using Amazon EMR's S3 layout.

Official layout and execution-mode references:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from mystack.aws_protocol.observability import log_event

_LOGGER = logging.getLogger(__name__)
_SAFE_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]")
_PUBLICATION_RECORD = "log-publication.json"


class LogStoreConfiguration(Protocol):
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    s3_path_style: bool


class ObjectWriter(Protocol):
    def put_object(self, **kwargs: Any) -> Any: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class StepLogPublicationRequest:
    cluster_id: str
    step_id: str
    log_uri: str | None
    work_dir: Path
    process_started: bool
    exit_code: int | None
    reason: str
    stdout_file: Path | None
    stderr_file: Path | None


class StepLogPublisher(Protocol):
    async def publish(self, request: StepLogPublicationRequest) -> None: ...


class S3StepLogPublisher:
    """Archive process logs without changing the Step execution outcome."""

    def __init__(
        self,
        settings: LogStoreConfiguration,
        *,
        client: ObjectWriter | None = None,
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

    async def publish(self, request: StepLogPublicationRequest) -> None:
        if request.log_uri is None:
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.step_logs.publish.skipped",
                cluster_id=request.cluster_id,
                step_id=request.step_id,
                reason="LogUri is not configured",
                side_effect=False,
            )
            await self._write_record(
                request, {"status": "skipped", "reason": "LogUri is not configured"}
            )
            return

        published_keys: list[str] = []
        try:
            if self._closed:
                raise RuntimeError("EMR Step log publisher is closed")
            destination = _destination(request.log_uri, request.cluster_id, request.step_id)
            payloads = await _payloads(request, destination)
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.step_logs.publish.before",
                cluster_id=request.cluster_id,
                step_id=request.step_id,
                bucket=destination.bucket,
                step_prefix=destination.step_prefix,
                application_prefix=destination.application_prefix,
                object_count=len(payloads),
                side_effect=True,
            )
            for key, payload in payloads:
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.step_log_object.put.before",
                    cluster_id=request.cluster_id,
                    step_id=request.step_id,
                    bucket=destination.bucket,
                    key=key,
                    uncompressed_bytes=len(payload),
                    side_effect=True,
                )
                compressed = gzip.compress(payload, mtime=0)
                await asyncio.to_thread(
                    self._client.put_object,
                    Bucket=destination.bucket,
                    Key=key,
                    Body=compressed,
                    ContentEncoding="gzip",
                    ContentType="text/plain; charset=utf-8",
                )
                published_keys.append(key)
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.step_log_object.put.after",
                    cluster_id=request.cluster_id,
                    step_id=request.step_id,
                    bucket=destination.bucket,
                    key=key,
                    compressed_bytes=len(compressed),
                    side_effect=True,
                )
        except Exception as error:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.step_logs.publish.failed",
                cluster_id=request.cluster_id,
                step_id=request.step_id,
                log_uri=request.log_uri,
                published_object_count=len(published_keys),
                reason_type=type(error).__name__,
                fix_hint=(
                    "Verify RunJobFlow.LogUri, bucket existence, LocalStack connectivity, "
                    "credentials, and S3 addressing configuration. The Spark result is preserved."
                ),
                exc_info=True,
            )
            await self._write_record(
                request,
                {
                    "status": "failed",
                    "log_uri": request.log_uri,
                    "published_keys": published_keys,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            return

        await self._write_record(
            request,
            {
                "status": "published",
                "log_uri": request.log_uri,
                "application_id": destination.application_id,
                "container_id": destination.container_id,
                "runtime_mode": "Spark local/client mode (synthetic application identifiers)",
                "published_keys": published_keys,
            },
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_logs.publish.after",
            cluster_id=request.cluster_id,
            step_id=request.step_id,
            bucket=destination.bucket,
            object_count=len(published_keys),
            side_effect=True,
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        log_event(_LOGGER, logging.INFO, "emr.step_log_publisher.close.before", side_effect=True)
        await asyncio.to_thread(self._client.close)
        log_event(_LOGGER, logging.INFO, "emr.step_log_publisher.close.after", side_effect=True)

    async def _write_record(
        self,
        request: StepLogPublicationRequest,
        publication: dict[str, Any],
    ) -> None:
        record = {
            "schema_version": 1,
            "cluster_id": request.cluster_id,
            "step_id": request.step_id,
            "process_started": request.process_started,
            "exit_code": request.exit_code,
            **publication,
        }
        target = request.work_dir / _PUBLICATION_RECORD
        temporary = target.with_suffix(".tmp")
        try:
            request.work_dir.mkdir(parents=True, exist_ok=True)
            content = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            await asyncio.to_thread(temporary.write_text, content, encoding="utf-8")
            await asyncio.to_thread(temporary.replace, target)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.step_logs.publication_record.failed",
                cluster_id=request.cluster_id,
                step_id=request.step_id,
                record_file=str(target),
                fix_hint="Verify that the configured EMR work_root is writable by hadoop.",
                exc_info=True,
            )


@dataclass(frozen=True, slots=True)
class _LogDestination:
    bucket: str
    step_prefix: str
    application_prefix: str
    application_id: str
    container_id: str


def _destination(log_uri: str, cluster_id: str, step_id: str) -> _LogDestination:
    parsed = urlparse(log_uri)
    if parsed.scheme != "s3" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("RunJobFlow.LogUri must be an s3://bucket[/prefix] URI")
    prefix = parsed.path.strip("/")
    application_id = f"application_local_{_identifier(cluster_id)}_{_identifier(step_id)}"
    container_id = f"container_local_{_identifier(cluster_id)}_{_identifier(step_id)}_01_000001"
    base = posixpath.join(prefix, cluster_id) if prefix else cluster_id
    return _LogDestination(
        bucket=parsed.netloc,
        step_prefix=posixpath.join(base, "steps", step_id),
        application_prefix=posixpath.join(base, "containers", application_id, container_id),
        application_id=application_id,
        container_id=container_id,
    )


async def _payloads(
    request: StepLogPublicationRequest,
    destination: _LogDestination,
) -> list[tuple[str, bytes]]:
    stdout, stderr = await asyncio.gather(
        _read(request.stdout_file),
        _read(request.stderr_file),
    )
    controller = (
        "Mystack EMR local Step controller projection\n"
        f"cluster_id={request.cluster_id}\n"
        f"step_id={request.step_id}\n"
        f"process_started={str(request.process_started).lower()}\n"
        f"exit_code={request.exit_code if request.exit_code is not None else 'unavailable'}\n"
    ).encode()
    syslog = (
        "Mystack EMR local runtime projection; no EC2, YARN, or node syslog was created.\n"
        f"reason={request.reason}\n"
    ).encode()
    return [
        (posixpath.join(destination.step_prefix, "controller.gz"), controller),
        (posixpath.join(destination.step_prefix, "syslog.gz"), syslog),
        (posixpath.join(destination.step_prefix, "stdout.gz"), stdout),
        (posixpath.join(destination.step_prefix, "stderr.gz"), stderr),
        (posixpath.join(destination.application_prefix, "stdout.gz"), stdout),
        (posixpath.join(destination.application_prefix, "stderr.gz"), stderr),
    ]


async def _read(path: Path | None) -> bytes:
    if path is None or not path.exists():
        return b""
    return await asyncio.to_thread(path.read_bytes)


def _identifier(value: str) -> str:
    return _SAFE_IDENTIFIER.sub("_", value)
