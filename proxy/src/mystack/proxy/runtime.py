"""Own the Proxy HTTP pool and its typed forwarding capabilities.

HTTPX client lifecycle reference:
https://www.python-httpx.org/advanced/clients/#opening-and-closing-clients
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from enum import StrEnum

import httpx
from mystack.aws_protocol.observability import log_event

from .config import ProxySettings, ServiceRoute
from .forwarder import AwsRequestForwarder, HttpManagementForwarder, HttpServiceUiForwarder
from .ports import (
    AwsRequestForwarding,
    ManagementForwarding,
    RouteDetector,
    ServiceUiForwarding,
)
from .routing import AwsServiceDetector

_LOGGER = logging.getLogger(__name__)

ClientFactory = Callable[[], httpx.AsyncClient]
DetectorFactory = Callable[[Sequence[ServiceRoute]], RouteDetector]


class RuntimeState(StrEnum):
    NEW = "NEW"
    STARTING = "STARTING"
    STARTED = "STARTED"
    FAILED = "FAILED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class ProxyRuntime:
    """Create, expose, and close one shared HTTP client exactly once."""

    def __init__(
        self,
        settings: ProxySettings,
        *,
        client: httpx.AsyncClient | None = None,
        client_factory: ClientFactory | None = None,
        detector_factory: DetectorFactory = AwsServiceDetector,
    ) -> None:
        if client is not None and client_factory is not None:
            raise ValueError("client and client_factory are mutually exclusive")
        self._settings = settings
        self._client_factory = client_factory or (
            (lambda: client)
            if client is not None
            else lambda: httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout_seconds))
        )
        self._detector_factory = detector_factory
        self._client: httpx.AsyncClient | None = None
        self._aws_requests: AwsRequestForwarding | None = None
        self._management: ManagementForwarding | None = None
        self._service_ui: ServiceUiForwarding | None = None
        self._state = RuntimeState.NEW
        self._closed = False
        self._close_lock = asyncio.Lock()

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def aws_requests(self) -> AwsRequestForwarding:
        if self._aws_requests is None:
            raise RuntimeError("Proxy runtime is not started")
        return self._aws_requests

    @property
    def management(self) -> ManagementForwarding:
        if self._management is None:
            raise RuntimeError("Proxy runtime is not started")
        return self._management

    @property
    def service_ui(self) -> ServiceUiForwarding:
        if self._service_ui is None:
            raise RuntimeError("Proxy runtime is not started")
        return self._service_ui

    async def start(self) -> None:
        if self._state is not RuntimeState.NEW:
            raise RuntimeError(f"Proxy runtime cannot start from {self._state}")
        self._state = RuntimeState.STARTING
        _log(logging.INFO, "proxy.runtime.start.before", side_effect=True)
        try:
            client = self._client_factory()
            if client is None:
                raise RuntimeError("Proxy HTTP client factory returned None")
            self._client = client
            detector = self._detector_factory(self._settings.routes)
            self._aws_requests = AwsRequestForwarder(client, self._settings, detector)
            self._management = HttpManagementForwarder(
                client,
                self._settings.routes,
            )
            self._service_ui = HttpServiceUiForwarder(client, self._settings.routes)
        except Exception:
            self._state = RuntimeState.FAILED
            _log(
                logging.ERROR,
                "proxy.runtime.start.failed",
                state=self._state,
                side_effect=True,
                fix_hint=(
                    "Inspect the configured HTTP client and route detector construction; "
                    "the runtime closed any client created before startup failed."
                ),
                exc_info=True,
            )
            await self.aclose()
            raise
        self._state = RuntimeState.STARTED
        _log(logging.INFO, "proxy.runtime.start.after", state=self._state, side_effect=True)

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._closed:
                _log(
                    logging.DEBUG,
                    "proxy.runtime.close.skipped",
                    state=self._state,
                    reason="already-closed",
                )
                return
            self._closed = True
            previous_state = self._state
            self._state = RuntimeState.CLOSING
            _log(
                logging.INFO,
                "proxy.runtime.close.before",
                previous_state=previous_state,
                client_created=self._client is not None,
                side_effect=True,
            )
            try:
                if self._client is not None:
                    await self._client.aclose()
            except Exception:
                self._state = RuntimeState.CLOSED
                _log(
                    logging.ERROR,
                    "proxy.runtime.close.failed",
                    side_effect=True,
                    fix_hint=(
                        "Inspect the HTTPX transport close path; no second close is attempted."
                    ),
                    exc_info=True,
                )
                raise
            self._state = RuntimeState.CLOSED
            _log(
                logging.INFO,
                "proxy.runtime.close.after",
                state=self._state,
                side_effect=True,
            )


def _log(level: int, event: str, *, exc_info: bool = False, **fields: object) -> None:
    log_event(_LOGGER, level, event, exc_info=exc_info, **fields)
