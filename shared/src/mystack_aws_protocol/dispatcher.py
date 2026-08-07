"""Operation dispatch boundary.

Operation names come from official botocore service models:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .context import AwsRequestContext
from .errors import AwsServiceError
from .observability import log_event

_LOGGER = logging.getLogger(__name__)

OperationHandler = Callable[[Mapping[str, Any], AwsRequestContext], Awaitable[Mapping[str, Any]]]


class OperationDispatcher:
    """Explicit operation-to-use-case mapping for an inbound AWS adapter."""

    def __init__(self, handlers: Mapping[str, OperationHandler] | None = None) -> None:
        self._handlers: dict[str, OperationHandler] = dict(handlers or {})

    def register(self, operation: str, handler: OperationHandler) -> None:
        if operation in self._handlers:
            raise ValueError(f"handler already registered for {operation}")
        self._handlers[operation] = handler

    @property
    def operations(self) -> frozenset[str]:
        return frozenset(self._handlers)

    async def dispatch(
        self,
        operation: str,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        handler = self._handlers.get(operation)
        if handler is None:
            log_event(
                _LOGGER,
                logging.WARNING,
                "application.dispatch.unsupported",
                service=context.service,
                operation=operation,
                request_id=context.request_id,
                fix_hint="Register the operation in the service inbound adapter dispatcher.",
            )
            raise AwsServiceError(
                "OperationNotImplementedException",
                f"The {operation} operation is recognized but is not implemented by Mystack yet.",
                http_status=501,
            )
        started = time.monotonic()
        log_event(
            _LOGGER,
            logging.INFO,
            "application.dispatch.started",
            service=context.service,
            operation=operation,
            request_id=context.request_id,
            input_members=sorted(payload),
        )
        try:
            result = await handler(payload, context)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "application.dispatch.failed",
                service=context.service,
                operation=operation,
                request_id=context.request_id,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "application.dispatch.completed",
            service=context.service,
            operation=operation,
            request_id=context.request_id,
            output_members=sorted(result),
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return result
