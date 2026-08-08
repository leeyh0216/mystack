"""Typed Build, Start, and Close ownership for the EMR service runtime.

Python lifecycle references:
https://docs.python.org/3/library/asyncio-task.html#task-cancellation
https://docs.python.org/3/library/asyncio-subprocess.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from mystack.aws_protocol.observability import log_event

from .application import EmrApplication

_LOGGER = logging.getLogger(__name__)


class RuntimeState(StrEnum):
    BUILT = "built"
    STARTED = "started"
    CLOSED = "closed"


class RuntimeSettings(Protocol):
    work_root: Path
    shutdown_timeout_seconds: float


class ProcessExecutorLifecycle(Protocol):
    @property
    def active_process_count(self) -> int: ...

    async def close(self) -> None: ...


class AsyncCloseable(Protocol):
    async def close(self) -> None: ...


class StartupProvisioning(Protocol):
    async def provision(self) -> tuple[object, ...]: ...


@dataclass(slots=True)
class EmrRuntime:
    """Own service resources and close consumers before their dependencies."""

    application: EmrApplication
    _executor: ProcessExecutorLifecycle
    _artifacts: AsyncCloseable
    _logs: AsyncCloseable
    _startup: StartupProvisioning
    _settings: RuntimeSettings
    _state: RuntimeState = RuntimeState.BUILT

    @classmethod
    def build(
        cls,
        application: EmrApplication,
        executor: ProcessExecutorLifecycle,
        artifacts: AsyncCloseable,
        logs: AsyncCloseable,
        startup: StartupProvisioning,
        settings: RuntimeSettings,
    ) -> EmrRuntime:
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.runtime.built",
            work_root=str(settings.work_root),
            shutdown_timeout_seconds=settings.shutdown_timeout_seconds,
            side_effect=False,
        )
        return cls(application, executor, artifacts, logs, startup, settings)

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def active_process_count(self) -> int:
        return self._executor.active_process_count

    async def start(self) -> None:
        if self._state is RuntimeState.CLOSED:
            raise RuntimeError("EMR runtime is closed")
        if self._state is RuntimeState.STARTED:
            return
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.runtime.start.before",
            work_root=str(self._settings.work_root),
            side_effect=True,
        )
        try:
            self._settings.work_root.mkdir(parents=True, exist_ok=True)
            await self.application.start()
            startup_clusters = await self._startup.provision()
        except BaseException:
            try:
                await self.close()
            except BaseException:
                log_event(
                    _LOGGER,
                    logging.ERROR,
                    "emr.runtime.partial_startup.cleanup.failed",
                    fix_hint=(
                        "Inspect resource close events; the original startup error is preserved."
                    ),
                    exc_info=True,
                )
            raise
        self._state = RuntimeState.STARTED
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.runtime.start.after",
            work_root=str(self._settings.work_root),
            startup_cluster_count=len(startup_clusters),
            side_effect=True,
        )

    async def close(self) -> None:
        if self._state is RuntimeState.CLOSED:
            return
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.runtime.close.before",
            runtime_state=self._state,
            active_process_count=self.active_process_count,
            side_effect=True,
        )
        first_error: BaseException | None = None
        for resource_name, close in (
            ("application", self.application.close),
            ("process_executor", self._executor.close),
            ("step_log_publisher", self._logs.close),
            ("artifact_store", self._artifacts.close),
        ):
            try:
                await close()
            except BaseException as error:
                first_error = first_error or error
                log_event(
                    _LOGGER,
                    logging.ERROR,
                    "emr.runtime.resource.close.failed",
                    resource_name=resource_name,
                    reason_type=type(error).__name__,
                    fix_hint="Inspect the preceding scheduler, process, and artifact close events.",
                    exc_info=True,
                )
        self._state = RuntimeState.CLOSED
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.runtime.close.after",
            active_process_count=self.active_process_count,
            side_effect=True,
        )
        if first_error is not None:
            raise first_error
