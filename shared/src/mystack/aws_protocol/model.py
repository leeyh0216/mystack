"""Pinned official SDK model facade and server-side shape validation.

Reference implementation and data:
https://github.com/boto/botocore/tree/develop/botocore/data

Pattern semantics:
https://smithy.io/2.0/spec/constraint-traits.html#pattern-trait
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import Any, ClassVar

import botocore
import botocore.session
from botocore.model import OperationModel, ServiceModel
from botocore.validate import ParamValidator
from mystack.aws_protocol.errors import AwsServiceError
from mystack.aws_protocol.observability import log_event

_LOGGER = logging.getLogger(__name__)
_LEGACY_SURROGATE_PAIR_RANGE = r"\uD800\uDC00-\uDBFF\uDFFF"
_PYTHON_ASTRAL_RANGE = r"\U00010000-\U0010FFFF"
_UNICODE_CATEGORY_CLASS = re.compile(
    r"^\[(?P<categories>(?:\\p\{[A-Z][a-z]?\})+)\](?P<quantifier>[*+?]?)$"
)
_UNICODE_CATEGORY = re.compile(r"\\p\{(?P<category>[A-Z][a-z]?)\}")


@dataclass(frozen=True, slots=True)
class AwsServiceMetadata:
    service_name: str
    api_version: str
    endpoint_prefix: str
    json_version: str
    target_prefix: str
    signing_name: str


class AwsServiceModel:
    """Read-only facade over the pinned official botocore service model."""

    _INVALID_INPUT_ERRORS: ClassVar[dict[str, str]] = {
        "glue": "InvalidInputException",
        "emr": "ValidationException",
    }

    def __init__(self, service_name: str) -> None:
        self._service_name = service_name

    @cached_property
    def description(self) -> dict[str, Any]:
        loader = botocore.session.get_session().get_component("data_loader")
        return loader.load_service_model(self._service_name, "service-2")

    @cached_property
    def raw(self) -> ServiceModel:
        unsupported_patterns = _unsupported_patterns(self.description)
        if unsupported_patterns:
            log_event(
                _LOGGER,
                logging.ERROR,
                "protocol.model.pattern_dialect_unsupported",
                service=self._service_name,
                botocore_version=botocore.__version__,
                shape_names=unsupported_patterns,
                fix_hint=(
                    "Add a generic ECMA-262 translation in shared/model.py and its protocol "
                    "contract before accepting this botocore model."
                ),
            )
            raise RuntimeError(
                "Unsupported service-model pattern dialect in shapes: "
                + ", ".join(unsupported_patterns)
            )
        model = ServiceModel(self.description, service_name=self._service_name)
        log_event(
            _LOGGER,
            logging.INFO,
            "protocol.model.loaded",
            service=self._service_name,
            botocore_version=botocore.__version__,
            api_version=model.api_version,
            operation_count=len(model.operation_names),
            model_fingerprint=self.fingerprint,
            model_source="botocore/data/<service>/<api-version>/service-2",
            fix_hint=(
                "If this fingerprint changed, run the coverage drift test and update the service "
                "inbound mappings plus documented compatibility matrix."
            ),
        )
        return model

    @cached_property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.description, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @cached_property
    def metadata(self) -> AwsServiceMetadata:
        raw_metadata: dict[str, Any] = self.raw.metadata
        endpoint_prefix = str(raw_metadata["endpointPrefix"])
        return AwsServiceMetadata(
            service_name=self._service_name,
            api_version=str(raw_metadata["apiVersion"]),
            endpoint_prefix=endpoint_prefix,
            json_version=str(raw_metadata["jsonVersion"]),
            target_prefix=str(raw_metadata["targetPrefix"]),
            signing_name=str(raw_metadata.get("signingName", endpoint_prefix)),
        )

    @property
    def operation_names(self) -> tuple[str, ...]:
        return tuple(self.raw.operation_names)

    def operation(self, name: str) -> OperationModel:
        if name not in self.raw.operation_names:
            raise AwsServiceError(
                "UnknownOperationException",
                f"Unknown operation {name}",
                http_status=404,
            )
        return self.raw.operation_model(name)

    def validate(self, operation: OperationModel, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise AwsServiceError(
                "SerializationException",
                "Start of structure or map found where not expected.",
            )
        input_shape = operation.input_shape
        if input_shape is None:
            if payload:
                self._invalid(operation.name, "Request must be empty")
            return
        errors = ParamValidator().validate(payload, input_shape)
        constraint_errors = _constraint_errors(payload, input_shape)
        if errors.has_errors() or constraint_errors:
            base_report = errors.generate_report() if errors.has_errors() else ""
            report = "\n".join(part for part in (base_report, *constraint_errors) if part)
            log_event(
                _LOGGER,
                logging.WARNING,
                "protocol.validation.failed",
                service=self._service_name,
                operation=operation.name,
                input_shape=input_shape.name,
                botocore_version=botocore.__version__,
                api_version=self.metadata.api_version,
                model_fingerprint=self.fingerprint,
                validation_error_count=len(report.splitlines()),
                model_constraint_error_count=len(constraint_errors),
                fix_hint=(
                    "Compare the pinned botocore input shape and AWS API Reference; update "
                    "shared/model.py only for generic codec behavior, otherwise update the "
                    "service operation mapper."
                ),
            )
            self._invalid(operation.name, report)

    def validate_output(self, operation: OperationModel, payload: Any) -> None:
        """Reject protocol-incompatible handler or extension output before serialization."""

        if not isinstance(payload, dict | Mapping):
            self._invalid_output(operation.name, "Response must be a mapping")
        output_shape = operation.output_shape
        if output_shape is None:
            if payload:
                self._invalid_output(operation.name, "Response must be empty")
            return
        errors = ParamValidator().validate(dict(payload), output_shape)
        constraint_errors = _constraint_errors(payload, output_shape, path="output")
        if not errors.has_errors() and not constraint_errors:
            return
        base_report = errors.generate_report() if errors.has_errors() else ""
        report = "\n".join(part for part in (base_report, *constraint_errors) if part)
        log_event(
            _LOGGER,
            logging.ERROR,
            "protocol.output_validation.failed",
            service=self._service_name,
            operation=operation.name,
            output_shape=output_shape.name,
            botocore_version=botocore.__version__,
            api_version=self.metadata.api_version,
            model_fingerprint=self.fingerprint,
            validation_error_count=len(report.splitlines()),
            fix_hint=(
                "Inspect the built-in handler or configured operation extension that produced "
                "the response; compare it with the pinned operation output shape."
            ),
        )
        self._invalid_output(operation.name, report)

    def _invalid(self, operation: str, message: str) -> None:
        error_code = self._INVALID_INPUT_ERRORS.get(self._service_name, "ValidationException")
        raise AwsServiceError(
            error_code,
            f"{operation}: {message}",
            fix_hint="Review the operation input shape in the pinned botocore service model.",
        )

    @staticmethod
    def _invalid_output(operation: str, message: str) -> None:
        del message
        raise AwsServiceError(
            "InternalServiceException",
            f"{operation}: an internal handler produced an invalid modeled response",
            http_status=500,
            fix_hint=(
                "Review the pinned operation output shape and the redacted output-validation "
                "event and inspect the registered inbound operation handler."
            ),
        )


def _constraint_errors(value: Any, shape: Any, path: str = "input") -> list[str]:
    """Validate constraints intentionally omitted by botocore's client validator."""

    errors: list[str] = []
    if shape.type_name == "string" and isinstance(value, str):
        errors.extend(_maximum_errors(len(value), shape, path, "length"))
        allowed = shape.metadata.get("enum")
        if allowed and value not in allowed:
            errors.append(
                f"Invalid enum for parameter {path}; must be one of: {', '.join(allowed)}"
            )
        pattern = shape.metadata.get("pattern")
        if pattern and not _matches_pattern(value, pattern):
            errors.append(f"Invalid format for parameter {path}; must satisfy modeled pattern")
    elif shape.type_name == "structure" and isinstance(value, dict):
        for name, member in shape.members.items():
            if name in value:
                errors.extend(_constraint_errors(value[name], member, f"{path}.{name}"))
    elif shape.type_name == "list" and isinstance(value, list | tuple):
        errors.extend(_maximum_errors(len(value), shape, path, "member count"))
        for index, member in enumerate(value):
            errors.extend(_constraint_errors(member, shape.member, f"{path}[{index}]"))
    elif shape.type_name == "map" and isinstance(value, dict):
        errors.extend(_maximum_errors(len(value), shape, path, "entry count"))
        for key, member in value.items():
            errors.extend(_constraint_errors(key, shape.key, f"{path} (key)"))
            errors.extend(_constraint_errors(member, shape.value, f"{path}.{key}"))
    elif (
        shape.type_name in {"integer", "long", "float", "double"}
        and isinstance(value, int | float)
        and not isinstance(value, bool)
    ):
        errors.extend(_maximum_errors(value, shape, path, "value"))
    return errors


def _maximum_errors(
    actual: int | float,
    shape: Any,
    path: str,
    measurement: str,
) -> list[str]:
    """Enforce modeled maxima that botocore deliberately omits client-side."""

    maximum = shape.metadata.get("max")
    if maximum is None or actual <= maximum:
        return []
    return [f"Invalid {measurement} for parameter {path}; must be less than or equal to {maximum}"]


def _matches_pattern(value: str, pattern: str) -> bool:
    translated = pattern.replace(_LEGACY_SURROGATE_PAIR_RANGE, _PYTHON_ASTRAL_RANGE)
    try:
        return re.search(translated, value) is not None
    except re.error:
        category_class = _UNICODE_CATEGORY_CLASS.fullmatch(pattern)
        if category_class is None:
            raise
        quantifier = category_class.group("quantifier")
        if quantifier in {"*", "?"}:
            return True
        categories = {
            match.group("category")
            for match in _UNICODE_CATEGORY.finditer(category_class.group("categories"))
        }
        return any(
            any(unicodedata.category(character).startswith(category) for category in categories)
            for character in value
        )


def _unsupported_patterns(description: dict[str, Any]) -> tuple[str, ...]:
    unsupported: list[str] = []
    for name, shape in description.get("shapes", {}).items():
        pattern = shape.get("pattern")
        if not pattern:
            continue
        translated = pattern.replace(_LEGACY_SURROGATE_PAIR_RANGE, _PYTHON_ASTRAL_RANGE)
        try:
            re.compile(translated)
        except re.error:
            if _UNICODE_CATEGORY_CLASS.fullmatch(pattern) is None:
                unsupported.append(str(name))
    return tuple(sorted(unsupported))
