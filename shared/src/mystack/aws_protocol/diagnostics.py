"""Operational thread and asyncio stack diagnostics for management endpoints.

Python references:
- https://docs.python.org/3/library/sys.html#sys._current_frames
- https://docs.python.org/3/library/threading.html
- https://docs.python.org/3/library/asyncio-task.html#introspection

Only frame metadata and source lines are returned. Frame locals are deliberately excluded.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .configuration import ConfigurationError, LoadedConfiguration, require_mapping
from .observability import log_event

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiagnosticsSettings:
    enabled: bool
    management_token: str | None
    stack_limit: int

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> DiagnosticsSettings:
        management = require_mapping(loaded.document, "management")
        diagnostics = require_mapping(management, "diagnostics")
        try:
            settings = cls(
                enabled=bool(diagnostics["enabled"]),
                management_token=(str(diagnostics["token"]) if diagnostics.get("token") else None),
                stack_limit=int(diagnostics["stack_limit"]),
            )
        except KeyError as error:
            raise ConfigurationError(
                f"management.diagnostics is missing required key: {error.args[0]}"
            ) from error
        if settings.stack_limit < 1:
            raise ConfigurationError("management.diagnostics.stack_limit must be at least 1")
        return settings


def create_diagnostics_router(service: str, settings: DiagnosticsSettings) -> APIRouter:
    router = APIRouter(prefix="/_mystack/diagnostics", tags=["Mystack diagnostics"])

    @router.get("/threads")
    async def threads(request: Request) -> dict[str, object]:
        authorize_management(request, settings, service, "threads")
        frames = sys._current_frames()
        live_threads = {thread.ident: thread for thread in threading.enumerate()}
        entries: list[dict[str, object]] = []
        for thread_id, frame in sorted(frames.items(), key=lambda item: item[0]):
            thread = live_threads.get(thread_id)
            entries.append(
                {
                    "thread_id": thread_id,
                    "name": thread.name if thread else "unknown",
                    "daemon": thread.daemon if thread else None,
                    "alive": thread.is_alive() if thread else None,
                    "stack": _format_stack(frame, settings.stack_limit),
                }
            )
        log_event(
            _LOGGER,
            logging.INFO,
            "diagnostics.threads.captured",
            service=service,
            thread_count=len(entries),
            client=_client(request),
        )
        return {
            "service": service,
            "captured_at": datetime.now(UTC).isoformat(),
            "thread_count": len(entries),
            "threads": entries,
            "warning": "Stack source lines are operationally sensitive; frame locals are excluded.",
        }

    @router.get("/tasks")
    async def tasks(request: Request) -> dict[str, object]:
        authorize_management(request, settings, service, "tasks")
        current = asyncio.current_task()
        entries: list[dict[str, object]] = []
        for task in sorted(asyncio.all_tasks(), key=lambda item: item.get_name()):
            entries.append(
                {
                    "name": task.get_name(),
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                    "current": task is current,
                    "stack": [
                        line.rstrip("\n")
                        for frame in task.get_stack(limit=settings.stack_limit)
                        for line in traceback.format_stack(frame, limit=1)
                    ],
                }
            )
        log_event(
            _LOGGER,
            logging.INFO,
            "diagnostics.tasks.captured",
            service=service,
            task_count=len(entries),
            client=_client(request),
        )
        return {
            "service": service,
            "captured_at": datetime.now(UTC).isoformat(),
            "task_count": len(entries),
            "tasks": entries,
        }

    return router


def authorize_management(
    request: Request,
    settings: DiagnosticsSettings,
    service: str,
    capability: str,
) -> None:
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="Diagnostics are disabled")
    if settings.management_token:
        supplied = request.headers.get("authorization", "")
        if supplied != f"Bearer {settings.management_token}":
            log_event(
                _LOGGER,
                logging.WARNING,
                "management.access.denied",
                service=service,
                capability=capability,
                client=_client(request),
            )
            raise HTTPException(status_code=401, detail="Invalid management token")
    log_event(
        _LOGGER,
        logging.INFO,
        "management.access.granted",
        service=service,
        capability=capability,
        client=_client(request),
        token_required=settings.management_token is not None,
    )


def _format_stack(frame: Any, limit: int) -> list[str]:
    return [line.rstrip("\n") for line in traceback.format_stack(frame, limit=limit)]


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"
