"""Operation dispatch boundary.

Operation names come from official botocore service models:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

from .context import AwsRequestContext
from .errors import AwsServiceError
from .extensions import OperationCall, OperationExtensionBinding, OperationNext
from .observability import log_event

_LOGGER = logging.getLogger(__name__)

OperationHandler = Callable[[Mapping[str, Any], AwsRequestContext], Awaitable[Mapping[str, Any]]]


class OperationDispatcher:
    """Explicit operation-to-use-case mapping for an inbound AWS adapter."""

    def __init__(
        self,
        handlers: Mapping[str, OperationHandler] | None = None,
        extensions: Iterable[OperationExtensionBinding] = (),
    ) -> None:
        self._handlers: dict[str, OperationHandler] = dict(handlers or {})
        self._extensions: list[OperationExtensionBinding] = []
        self._extension_ids: set[str] = set()
        for extension in extensions:
            self.register_extension(extension)

    def register(self, operation: str, handler: OperationHandler) -> None:
        if operation in self._handlers:
            raise ValueError(f"handler already registered for {operation}")
        self._handlers[operation] = handler

    def register_extension(self, extension: OperationExtensionBinding) -> None:
        if extension.extension_id in self._extension_ids:
            raise ValueError(f"extension already registered: {extension.extension_id}")
        self._extensions.append(extension)
        self._extensions.sort(key=lambda item: (item.priority, item.extension_id))
        self._extension_ids.add(extension.extension_id)

    @property
    def operations(self) -> frozenset[str]:
        selected = {
            operation
            for extension in self._extensions
            for operation in extension.operations
            if operation != "*"
        }
        return frozenset(self._handlers) | frozenset(selected)

    async def dispatch(
        self,
        operation: str,
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        extensions = [
            extension
            for extension in self._extensions
            if operation in extension.operations or "*" in extension.operations
        ]
        started = time.monotonic()
        log_event(
            _LOGGER,
            logging.INFO,
            "application.dispatch.started",
            service=context.service,
            operation=operation,
            request_id=context.request_id,
            input_members=sorted(payload),
            extension_count=len(extensions),
            extension_ids=[extension.extension_id for extension in extensions],
        )
        try:
            result = await self._invoke_chain(
                extensions,
                OperationCall(operation=operation, payload=payload, context=context),
            )
        except AwsServiceError as error:
            log_event(
                _LOGGER,
                logging.WARNING,
                "application.dispatch.service_error",
                service=context.service,
                operation=operation,
                request_id=context.request_id,
                error_code=error.code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            raise
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

    async def _invoke_chain(
        self,
        extensions: list[OperationExtensionBinding],
        call: OperationCall,
    ) -> Mapping[str, Any]:
        async def invoke_at(index: int, current: OperationCall) -> Mapping[str, Any]:
            if index == len(extensions):
                return await self._invoke_builtin(current)
            extension = extensions[index]
            next_called = False

            async def next_handler(next_call: OperationCall) -> Mapping[str, Any]:
                nonlocal next_called
                if next_called:
                    raise RuntimeError(
                        f"extension {extension.extension_id!r} called next more than once"
                    )
                if next_call.operation != call.operation or next_call.context is not call.context:
                    raise ValueError(
                        f"extension {extension.extension_id!r} may only replace the payload"
                    )
                next_called = True
                return await invoke_at(index + 1, next_call)

            return await self._invoke_extension(extension, current, next_handler)

        return await invoke_at(0, call)

    async def _invoke_builtin(self, call: OperationCall) -> Mapping[str, Any]:
        handler = self._handlers.get(call.operation)
        if handler is not None:
            return await handler(call.payload, call.context)
        log_event(
            _LOGGER,
            logging.WARNING,
            "application.dispatch.unsupported",
            service=call.context.service,
            operation=call.operation,
            request_id=call.context.request_id,
            fix_hint=(
                "Register the operation in the service inbound adapter or let an extension "
                "return a complete modeled response without calling next."
            ),
        )
        raise AwsServiceError(
            "OperationNotImplementedException",
            f"The {call.operation} operation is recognized but is not implemented by Mystack yet.",
            http_status=501,
        )

    async def _invoke_extension(
        self,
        extension: OperationExtensionBinding,
        call: OperationCall,
        next_handler: OperationNext,
    ) -> Mapping[str, Any]:
        started = time.monotonic()
        fields = {
            "service": call.context.service,
            "operation": call.operation,
            "request_id": call.context.request_id,
            "extension_id": extension.extension_id,
            "extension_spi": extension.spi,
            "timeout_seconds": extension.timeout_seconds,
        }
        log_event(_LOGGER, logging.INFO, "extension.invoke.started", **fields)
        try:
            async with asyncio.timeout(extension.timeout_seconds):
                result = await extension.middleware.invoke(call, next_handler)
            if not isinstance(result, Mapping):
                raise TypeError(
                    f"extension {extension.extension_id!r} returned a non-mapping response"
                )
        except TimeoutError as error:
            log_event(
                _LOGGER,
                logging.ERROR,
                "extension.invoke.timed_out",
                **fields,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                fix_hint=(
                    "Increase this provider's configured timeout or remove blocking work from "
                    "its in-process operation middleware."
                ),
            )
            raise AwsServiceError(
                "InternalServiceException",
                "A configured Mystack extension exceeded its execution deadline.",
                http_status=500,
                fix_hint=f"Inspect extension {extension.extension_id!r} and its timeout setting.",
            ) from error
        except AwsServiceError as error:
            log_event(
                _LOGGER,
                logging.WARNING,
                "extension.invoke.service_error",
                **fields,
                error_code=error.code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            raise
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "extension.invoke.failed",
                **fields,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                fix_hint=(
                    "Inspect the configured extension entry point and the SPI context version."
                ),
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "extension.invoke.completed",
            **fields,
            output_members=sorted(result),
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return result
