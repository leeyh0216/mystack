"""Service-owned reconnectable EMR log stream over HTML Server-Sent Events.

References:
- https://html.spec.whatwg.org/multipage/server-sent-events.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import Request
from mystack.aws_protocol import ManagementUiSettings
from mystack.aws_protocol.observability import log_event

_LOGGER = logging.getLogger(__name__)


class LogChunkQueries(Protocol):
    async def log_chunk(
        self,
        cluster_id: str,
        step_id: str,
        *,
        stdout_offset: int,
        stderr_offset: int,
    ) -> dict[str, Any]: ...


class EmrLogEventStream:
    def __init__(self, logs: LogChunkQueries, settings: ManagementUiSettings) -> None:
        self._logs = logs
        self._poll_interval = settings.log_stream_poll_interval_seconds
        self._timeout = settings.log_stream_timeout_seconds

    async def events(
        self,
        request: Request,
        *,
        cluster_id: str,
        step_id: str,
        stdout_offset: int,
        stderr_offset: int,
    ) -> AsyncIterator[bytes]:
        stdout_offset, stderr_offset = offsets_from_last_event_id(
            request.headers.get("last-event-id"),
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
        )
        started = time.monotonic()
        deadline = started + self._timeout
        reason = "timeout"
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.ui.log_stream.open",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
            poll_interval_seconds=self._poll_interval,
            stream_timeout_seconds=self._timeout,
            side_effect=False,
        )
        yield f"retry: {max(100, round(self._poll_interval * 2000))}\n\n".encode()
        try:
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    reason = "client_disconnected"
                    return
                document = await self._logs.log_chunk(
                    cluster_id,
                    step_id,
                    stdout_offset=stdout_offset,
                    stderr_offset=stderr_offset,
                )
                stdout_offset = int(document["stdout_next_offset"])
                stderr_offset = int(document["stderr_next_offset"])
                if document.get("stdout") or document.get("stderr") or document.get("complete"):
                    yield _event(
                        "logs",
                        document,
                        event_id=f"{stdout_offset}:{stderr_offset}",
                    )
                else:
                    yield b": keep-alive\n\n"
                if document.get("complete"):
                    reason = "complete"
                    return
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            reason = "cancelled"
            raise
        except Exception as error:
            reason = "service_error"
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.ui.log_stream.failed",
                cluster_id=cluster_id,
                step_id=step_id,
                reason_type=type(error).__name__,
                fix_hint=(
                    "Inspect the EMR UI log-stream controller and management log-chunk schema; "
                    "the service owns both boundaries."
                ),
                exc_info=True,
            )
            yield _event("error", {"detail": "EMR log stream unavailable"})
        finally:
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.ui.log_stream.close",
                cluster_id=cluster_id,
                step_id=step_id,
                stdout_offset=stdout_offset,
                stderr_offset=stderr_offset,
                reason=reason,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                side_effect=False,
            )


def offsets_from_last_event_id(
    value: str | None,
    *,
    stdout_offset: int,
    stderr_offset: int,
) -> tuple[int, int]:
    if not value:
        return stdout_offset, stderr_offset
    try:
        saved_stdout, saved_stderr = value.split(":", maxsplit=1)
        return max(stdout_offset, int(saved_stdout)), max(stderr_offset, int(saved_stderr))
    except (TypeError, ValueError):
        return stdout_offset, stderr_offset


def _event(name: str, document: object, *, event_id: str | None = None) -> bytes:
    lines = [f"id: {event_id}"] if event_id else []
    lines.append(f"event: {name}")
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    lines.extend(f"data: {line}" for line in payload.splitlines() or [""])
    return ("\n".join(lines) + "\n\n").encode()
