"""Deterministic Glue domain-to-AWS error decisions at the inbound boundary.

Official errors: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mystack.aws_protocol import AwsRequestContext, AwsServiceError, OperationFamily
from mystack.aws_protocol.dispatcher import OperationHandler
from mystack.aws_protocol.observability import log_event
from mystack.glue.adapters.inbound.aws_faults import GlueFaultInjector
from mystack.glue.domain import (
    AlreadyExistsError,
    EntityNotFoundError,
    InvalidInputError,
    VersionMismatchError,
)
from mystack.glue.domain.errors import GlueDomainError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GlueErrorDecision:
    condition_id: str
    category: str
    phase: str
    error_code: str
    http_status: int
    mutation_guarantee: str


class GlueErrorTranslator:
    """Translate framework-free domain failures into one documented AWS decision."""

    _DOMAIN_DECISIONS = (
        (
            AlreadyExistsError,
            GlueErrorDecision(
                "resource.already_exists",
                "conflict",
                "duplicate_conflict",
                "AlreadyExistsException",
                400,
                "candidate_not_committed",
            ),
        ),
        (
            EntityNotFoundError,
            GlueErrorDecision(
                "resource.not_found",
                "not_found",
                "parent_existence",
                "EntityNotFoundException",
                400,
                "candidate_not_committed",
            ),
        ),
        (
            InvalidInputError,
            GlueErrorDecision(
                "input.value_invalid",
                "validation",
                "value_constraints",
                "InvalidInputException",
                400,
                "candidate_not_committed",
            ),
        ),
        (
            VersionMismatchError,
            GlueErrorDecision(
                "version.mismatch",
                "concurrency",
                "version_concurrency",
                "ConcurrentModificationException",
                400,
                "candidate_not_committed",
            ),
        ),
    )

    def decision(self, error: GlueDomainError) -> GlueErrorDecision:
        for error_type, decision in self._DOMAIN_DECISIONS:
            if isinstance(error, error_type):
                return decision
        raise TypeError(f"No Glue error decision registered for {type(error).__name__}")

    def detail(self, error: GlueDomainError) -> dict[str, str]:
        decision = self.decision(error)
        return {"ErrorCode": decision.error_code, "ErrorMessage": str(error)}

    def service_error(self, error: GlueDomainError) -> tuple[GlueErrorDecision, AwsServiceError]:
        decision = self.decision(error)
        return decision, AwsServiceError(
            decision.error_code,
            str(error),
            http_status=decision.http_status,
        )


class GlueErrorBoundary:
    """Own fault selection, error classification, logging, and AWS translation."""

    def __init__(
        self,
        translator: GlueErrorTranslator,
        fault_injector: GlueFaultInjector,
    ) -> None:
        self._translator = translator
        self._fault_injector = fault_injector

    def family(self, name: str, handlers: Mapping[str, OperationHandler]) -> OperationFamily:
        return OperationFamily(
            name,
            {
                operation: self._wrap(name, operation, handler)
                for operation, handler in handlers.items()
            },
        )

    def error_detail(self, error: GlueDomainError) -> dict[str, str]:
        return self._translator.detail(error)

    def _wrap(
        self,
        family: str,
        operation: str,
        handler: OperationHandler,
    ) -> OperationHandler:
        async def translated(
            payload: Mapping[str, Any],
            context: AwsRequestContext,
        ) -> Mapping[str, Any]:
            try:
                self._fault_injector.before_operation(context)
                return await handler(payload, context)
            except AwsServiceError:
                raise
            except GlueDomainError as error:
                decision, service_error = self._translator.service_error(error)
                self._log_decision(context, family, decision)
                service_error.fix_hint = (
                    f"Compare the Glue {family} operation family and domain invariant with the "
                    "machine-readable Glue error contract."
                )
                raise service_error from error
            except (KeyError, TypeError, ValueError) as error:
                decision = GlueErrorDecision(
                    "adapter.mapping_failure",
                    "system",
                    "mutation",
                    "InternalServiceException",
                    500,
                    "candidate_not_committed",
                )
                self._log_decision(
                    context,
                    family,
                    decision,
                    failure_type=type(error).__name__,
                )
                raise AwsServiceError(
                    decision.error_code,
                    "An internal Glue request mapping error occurred.",
                    http_status=decision.http_status,
                    fix_hint=(
                        f"Inspect the Glue {family} operation family for request-shape mapping "
                        f"drift in {operation}."
                    ),
                ) from error
            except OSError as error:
                decision = GlueErrorDecision(
                    "persistence.side_effect_failed",
                    "system",
                    "persistence_side_effect",
                    "InternalServiceException",
                    500,
                    "candidate_not_published",
                )
                self._log_decision(
                    context,
                    family,
                    decision,
                    failure_type=type(error).__name__,
                )
                raise AwsServiceError(
                    decision.error_code,
                    "An internal Glue persistence error occurred.",
                    http_status=decision.http_status,
                    fix_hint=(
                        "Inspect repository transaction logs; the failed candidate must remain "
                        "invisible and durable state must be unchanged."
                    ),
                ) from error

        return translated

    @staticmethod
    def _log_decision(
        context: AwsRequestContext,
        family: str,
        decision: GlueErrorDecision,
        *,
        failure_type: str | None = None,
    ) -> None:
        log_event(
            _LOGGER,
            logging.WARNING if decision.http_status < 500 else logging.ERROR,
            "glue.error.decision",
            service=context.service,
            operation=context.operation,
            operation_family=family,
            request_id=context.request_id,
            condition_id=decision.condition_id,
            category=decision.category,
            phase=decision.phase,
            error_code=decision.error_code,
            http_status=decision.http_status,
            mutation_guarantee=decision.mutation_guarantee,
            failure_type=failure_type,
        )


_DEFAULT_TRANSLATOR = GlueErrorTranslator()


def error_detail(error: GlueDomainError) -> dict[str, str]:
    """Translate batch item errors through the same immutable decision table."""

    return _DEFAULT_TRANSLATOR.detail(error)
