"""Glue family-local modeled error translation.

Official errors: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mystack.aws_protocol import AwsRequestContext, AwsServiceError, OperationFamily
from mystack.aws_protocol.dispatcher import OperationHandler
from mystack.glue.domain import (
    AlreadyExistsError,
    EntityNotFoundError,
    VersionMismatchError,
)
from mystack.glue.domain.errors import GlueDomainError


def glue_family(name: str, handlers: Mapping[str, OperationHandler]) -> OperationFamily:
    return OperationFamily(
        name,
        {operation: _translate(name, handler) for operation, handler in handlers.items()},
    )


def error_detail(error: GlueDomainError) -> dict[str, str]:
    return {"ErrorCode": error_code(error), "ErrorMessage": str(error)}


def error_code(error: GlueDomainError) -> str:
    if isinstance(error, AlreadyExistsError):
        return "AlreadyExistsException"
    if isinstance(error, EntityNotFoundError):
        return "EntityNotFoundException"
    if isinstance(error, VersionMismatchError):
        return "VersionMismatchException"
    return "InvalidInputException"


def _translate(family: str, handler: OperationHandler) -> OperationHandler:
    async def translated(
        payload: Mapping[str, Any],
        context: AwsRequestContext,
    ) -> Mapping[str, Any]:
        try:
            return await handler(payload, context)
        except GlueDomainError as error:
            raise AwsServiceError(
                error_code(error),
                str(error),
                http_status=400,
                fix_hint=(
                    f"Compare the Glue {family} operation family and domain invariant with the "
                    "pinned service model and AWS Glue API error list."
                ),
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            raise AwsServiceError(
                "InvalidInputException",
                str(error),
                http_status=400,
                fix_hint=(
                    f"Inspect the Glue {family} operation family for request-shape mapping drift."
                ),
            ) from error

    return translated
