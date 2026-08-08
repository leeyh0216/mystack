"""Validated operation-family registry for AWS service inbound adapters.

Operation names are defined by official botocore service models:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from mystack.aws_protocol.dispatcher import OperationDispatcher, OperationHandler
from mystack.aws_protocol.observability import log_event

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OperationFamily:
    name: str
    handlers: Mapping[str, OperationHandler]


class OperationFamilyRegistry:
    """Merge operation families and reject duplicate or coverage-incomplete registration."""

    def __init__(self, service: str, expected_operations: Iterable[str]) -> None:
        self._service = service
        self._expected = frozenset(expected_operations)

    def dispatcher(self, families: Iterable[OperationFamily]) -> OperationDispatcher:
        handlers: dict[str, OperationHandler] = {}
        owners: dict[str, str] = {}
        family_names: list[str] = []
        log_event(
            _LOGGER,
            logging.INFO,
            "protocol.operation_registry.build.before",
            service=self._service,
            expected_operation_count=len(self._expected),
            side_effect=False,
        )
        for family in families:
            if not family.name or not family.handlers:
                self._fail("family names and handler maps must be non-empty")
            family_names.append(family.name)
            for operation, handler in family.handlers.items():
                previous = owners.get(operation)
                if previous is not None:
                    self._fail(
                        f"operation {operation!r} is owned by both {previous!r} and {family.name!r}"
                    )
                owners[operation] = family.name
                handlers[operation] = handler
            log_event(
                _LOGGER,
                logging.INFO,
                "protocol.operation_registry.family.registered",
                service=self._service,
                family=family.name,
                operations=sorted(family.handlers),
                operation_count=len(family.handlers),
                side_effect=False,
            )
        actual = frozenset(handlers)
        missing = sorted(self._expected - actual)
        unexpected = sorted(actual - self._expected)
        if missing or unexpected:
            self._fail(f"coverage mismatch: missing={missing}, unexpected={unexpected}")
        log_event(
            _LOGGER,
            logging.INFO,
            "protocol.operation_registry.build.after",
            service=self._service,
            families=family_names,
            operation_count=len(handlers),
            side_effect=False,
        )
        return OperationDispatcher(handlers)

    def _fail(self, reason: str) -> None:
        log_event(
            _LOGGER,
            logging.ERROR,
            "protocol.operation_registry.build.failed",
            service=self._service,
            reason=reason,
            fix_hint=("Update the operation family and implemented API coverage classification."),
        )
        raise ValueError(f"Invalid {self._service} operation-family registry: {reason}")
