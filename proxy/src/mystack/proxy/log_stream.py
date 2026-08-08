"""Reconnectable EMR log stream over the HTML Server-Sent Events protocol.

The Proxy polls bounded backend chunks so component HTTP connections remain short-lived. Event IDs
carry byte offsets and can be supplied through ``Last-Event-ID`` after a reconnect.

References:
- https://html.spec.whatwg.org/multipage/server-sent-events.html
- https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import Request
from mystack.aws_protocol.observability import log_event

from .ports import ManagementForwarding

_LOGGER = logging.getLogger(__name__)


class LogStreamSettings(Protocol):
    console_log_stream_poll_interval_seconds: float
    console_log_stream_timeout_seconds: float


class EmrLogEventStream:
    def __init__(
        self,
        management: ManagementForwarding,
        settings: LogStreamSettings,
    ) -> None:
        self._management = management
        self._poll_interval = settings.console_log_stream_poll_interval_seconds
        self._stream_timeout = settings.console_log_stream_timeout_seconds

    async def events(
        self,
        request: Request,
        *,
        cluster_id: str,
        step_id: str,
        stdout_offset: int,
        stderr_offset: int,
        authorization: str | None,
    ) -> AsyncIterator[bytes]:
        started = time.monotonic()
        deadline = started + self._stream_timeout
        log_event(
            _LOGGER,
            logging.INFO,
            "proxy.emr_log_stream.open",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
            poll_interval_seconds=self._poll_interval,
            stream_timeout_seconds=self._stream_timeout,
            side_effect=False,
        )
        yield f"retry: {max(100, round(self._poll_interval * 2000))}\n\n".encode()
        reason = "timeout"
        try:
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    reason = "client_disconnected"
                    return
                response = await self._management.forward(
                    component="emr",
                    backend_path="/_mystack/management/logs/chunk",
                    capability="logs.stream.chunk",
                    authorization=authorization,
                    query_params=(
                        ("cluster_id", cluster_id),
                        ("step_id", step_id),
                        ("stdout_offset", str(stdout_offset)),
                        ("stderr_offset", str(stderr_offset)),
                    ),
                )
                if response.status_code != 200:
                    reason = "backend_error"
                    yield _event(
                        "error",
                        {
                            "status_code": response.status_code,
                            "detail": response.content.decode("utf-8", errors="replace"),
                        },
                    )
                    return
                try:
                    document = json.loads(response.content)
                    stdout_offset = int(document["stdout_next_offset"])
                    stderr_offset = int(document["stderr_next_offset"])
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                    reason = "protocol_error"
                    log_event(
                        _LOGGER,
                        logging.ERROR,
                        "proxy.emr_log_stream.protocol.failed",
                        cluster_id=cluster_id,
                        step_id=step_id,
                        reason_type=type(error).__name__,
                        backend_content_type=response.content_type,
                        fix_hint=(
                            "Compare the EMR /logs/chunk schema and this SSE adapter when the "
                            "component protocol version changes."
                        ),
                        exc_info=True,
                    )
                    yield _event("error", {"detail": "Invalid EMR log chunk protocol"})
                    return
                event_id = f"{stdout_offset}:{stderr_offset}"
                has_content = bool(document.get("stdout") or document.get("stderr"))
                if has_content or document.get("complete"):
                    yield _event("logs", document, event_id=event_id)
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
            reason = "gateway_error"
            log_event(
                _LOGGER,
                logging.ERROR,
                "proxy.emr_log_stream.failed",
                cluster_id=cluster_id,
                step_id=step_id,
                reason_type=type(error).__name__,
                fix_hint=(
                    "Check the declarative EMR route, component health, management token, and "
                    "the configured stream timeout."
                ),
                exc_info=True,
            )
            yield _event("error", {"detail": "EMR log stream gateway unavailable"})
        finally:
            log_event(
                _LOGGER,
                logging.INFO,
                "proxy.emr_log_stream.close",
                cluster_id=cluster_id,
                step_id=step_id,
                stdout_offset=stdout_offset,
                stderr_offset=stderr_offset,
                reason=reason,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                side_effect=False,
            )


def offsets_from_last_event_id(
    last_event_id: str | None,
    *,
    stdout_offset: int,
    stderr_offset: int,
) -> tuple[int, int]:
    if not last_event_id:
        return stdout_offset, stderr_offset
    try:
        saved_stdout, saved_stderr = last_event_id.split(":", maxsplit=1)
        return max(stdout_offset, int(saved_stdout)), max(stderr_offset, int(saved_stderr))
    except (ValueError, TypeError):
        return stdout_offset, stderr_offset


def _event(name: str, document: object, *, event_id: str | None = None) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {name}")
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    lines.extend(f"data: {line}" for line in payload.splitlines() or [""])
    return ("\n".join(lines) + "\n\n").encode()
