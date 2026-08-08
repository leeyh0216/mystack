"""EMR family-local domain and shape error translation.

Official error contract:
https://docs.aws.amazon.com/emr/latest/APIReference/API_InvalidRequestException.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.aws_protocol import AwsRequestContext, AwsServiceError, OperationFamily
from mystack.aws_protocol.dispatcher import OperationHandler
from mystack.emr.domain.errors import EmrDomainError


def emr_family(name: str, handlers: Mapping[str, OperationHandler]) -> OperationFamily:
    return OperationFamily(
        name,
        {operation: _translate(name, handler) for operation, handler in handlers.items()},
    )


def _translate(family: str, handler: OperationHandler) -> OperationHandler:
    async def translated(
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        try:
            return await handler(payload, context)
        except (EmrDomainError, KeyError, TypeError, ValueError) as error:
            raise AwsServiceError(
                "InvalidRequestException",
                str(error),
                http_status=400,
                fix_hint=(
                    f"Check the EMR {family} operation family against the pinned botocore model "
                    "and AWS EMR API Reference."
                ),
            ) from error

    return translated
