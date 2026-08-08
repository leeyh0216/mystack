"""Explicit deterministic Glue service-failure injection at the inbound boundary.

Official exception definitions:
https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

import logging
from collections.abc import Collection

from mystack.aws_protocol import AwsRequestContext, AwsServiceError, ConfigurationError
from mystack.aws_protocol.observability import log_event
from mystack.glue.application.policies import GlueFaultInjectionPolicy, GlueFaultRule

_LOGGER = logging.getLogger(__name__)
_INJECTABLE_ERRORS = {
    "InternalServiceException": 500,
    "OperationTimeoutException": 400,
}


class GlueFaultInjector:
    """Select at most one configured failure for an otherwise valid operation."""

    def __init__(
        self,
        policy: GlueFaultInjectionPolicy,
        supported_operations: Collection[str],
    ) -> None:
        supported = set(supported_operations)
        rules_by_operation: dict[str, GlueFaultRule] = {}
        rule_ids: set[str] = set()
        for rule in policy.rules:
            if not rule.rule_id.strip():
                raise ConfigurationError("Glue fault rule id cannot be empty")
            if not rule.message.strip():
                raise ConfigurationError(
                    f"Glue fault rule {rule.rule_id} response message cannot be empty"
                )
            if rule.rule_id in rule_ids:
                raise ConfigurationError(f"Duplicate Glue fault rule id: {rule.rule_id}")
            if rule.operation in rules_by_operation:
                raise ConfigurationError(
                    f"Glue fault injection has multiple rules for {rule.operation}"
                )
            if rule.operation not in supported:
                raise ConfigurationError(
                    f"Glue fault rule {rule.rule_id} uses unsupported operation {rule.operation}"
                )
            if rule.error_code not in _INJECTABLE_ERRORS:
                raise ConfigurationError(
                    f"Glue fault rule {rule.rule_id} uses forbidden error {rule.error_code}"
                )
            rule_ids.add(rule.rule_id)
            rules_by_operation[rule.operation] = rule
        self._enabled = policy.enabled
        self._rules_by_operation = rules_by_operation

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def rule_count(self) -> int:
        return len(self._rules_by_operation)

    def before_operation(self, context: AwsRequestContext) -> None:
        if not self._enabled:
            return
        rule = self._rules_by_operation.get(context.operation)
        if rule is None:
            return
        http_status = _INJECTABLE_ERRORS[rule.error_code]
        log_event(
            _LOGGER,
            logging.WARNING,
            "glue.error.decision",
            service=context.service,
            operation=context.operation,
            request_id=context.request_id,
            condition_id=f"fault.{_condition_suffix(rule.error_code)}",
            category="injectable",
            phase="fault_injection",
            error_code=rule.error_code,
            http_status=http_status,
            mutation_guarantee="handler_not_called",
            fault_rule_id=rule.rule_id,
            fix_hint=(
                "Disable or edit glue.fault_injection in the mounted configuration file after "
                "the deterministic failure scenario is complete."
            ),
        )
        raise AwsServiceError(
            rule.error_code,
            rule.message,
            http_status=http_status,
            fix_hint=f"Injected by configured Glue fault rule {rule.rule_id}.",
        )


def _condition_suffix(error_code: str) -> str:
    if error_code == "OperationTimeoutException":
        return "operation_timeout"
    return "internal_service"
