"""Operation extension chain contracts.

Python asynchronous timeout reference:
https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
"""

from __future__ import annotations

import asyncio

import pytest
from mystack_aws_protocol import (
    AwsRequestContext,
    AwsServiceError,
    OperationCall,
    OperationDispatcher,
    OperationExtensionBinding,
)


def _context(operation: str = "GetDatabase") -> AwsRequestContext:
    return AwsRequestContext(
        request_id="request-1",
        service="glue",
        operation=operation,
        region="us-east-1",
        account_id="000000000000",
    )


async def test_extensions_compose_in_priority_order_and_can_change_payload_and_result() -> None:
    events: list[str] = []

    class Outer:
        async def invoke(self, call, next_handler):
            events.append("outer.before")
            result = await next_handler(call.with_payload({"Name": "changed"}))
            events.append("outer.after")
            return {"Database": {**result["Database"], "Description": "outer"}}

    class Inner:
        async def invoke(self, call, next_handler):
            events.append("inner.before")
            result = await next_handler(call)
            events.append("inner.after")
            return result

    async def built_in(payload, context):
        events.append("built-in")
        return {"Database": {"Name": payload["Name"]}}

    dispatcher = OperationDispatcher(
        {"GetDatabase": built_in},
        extensions=(
            OperationExtensionBinding(
                "inner", "stable", frozenset({"GetDatabase"}), 20, 1, Inner()
            ),
            OperationExtensionBinding(
                "outer", "stable", frozenset({"GetDatabase"}), 10, 1, Outer()
            ),
        ),
    )

    result = await dispatcher.dispatch("GetDatabase", {"Name": "original"}, _context())

    assert result == {"Database": {"Name": "changed", "Description": "outer"}}
    assert events == [
        "outer.before",
        "inner.before",
        "built-in",
        "inner.after",
        "outer.after",
    ]


async def test_extension_can_replace_an_operation_without_a_builtin_handler() -> None:
    class Replacement:
        async def invoke(self, call, next_handler):
            return {"Database": {"Name": call.payload["Name"]}}

    dispatcher = OperationDispatcher(
        extensions=(
            OperationExtensionBinding(
                "replacement", "application", frozenset({"GetDatabase"}), 1, 1, Replacement()
            ),
        )
    )

    result = await dispatcher.dispatch("GetDatabase", {"Name": "replaced"}, _context())

    assert result == {"Database": {"Name": "replaced"}}
    assert dispatcher.operations == frozenset({"GetDatabase"})


async def test_extension_cannot_invoke_next_twice() -> None:
    class Invalid:
        async def invoke(self, call, next_handler):
            await next_handler(call)
            return await next_handler(call)

    async def built_in(payload, context):
        return {}

    dispatcher = OperationDispatcher(
        {"GetDatabase": built_in},
        extensions=(
            OperationExtensionBinding(
                "invalid", "unsafe", frozenset({"GetDatabase"}), 1, 1, Invalid()
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="called next more than once"):
        await dispatcher.dispatch("GetDatabase", {"Name": "db"}, _context())


async def test_extension_timeout_becomes_a_safe_service_error() -> None:
    class Slow:
        async def invoke(self, call: OperationCall, next_handler):
            await asyncio.sleep(1)
            return {}

    dispatcher = OperationDispatcher(
        extensions=(
            OperationExtensionBinding(
                "slow", "stable", frozenset({"GetDatabase"}), 1, 0.001, Slow()
            ),
        )
    )

    with pytest.raises(AwsServiceError) as captured:
        await dispatcher.dispatch("GetDatabase", {"Name": "db"}, _context())

    assert captured.value.code == "InternalServiceException"
    assert captured.value.http_status == 500
