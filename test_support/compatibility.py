"""Typed compatibility evidence declared next to pytest tests.

This module intentionally contains only value objects and a thin pytest-marker decorator.
It does not import Mystack service code, run tests, or interpret CI configuration.  That lets
the collection adapter remain an outer boundary while tests own the claims they make.

References:
- https://docs.pytest.org/en/stable/how-to/mark.html
- https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeVar

import pytest

_T = TypeVar("_T", bound=Callable[..., object])


class EvidenceValidationError(ValueError):
    """A test-declared compatibility claim is ambiguous or unsafe."""


class ExecutionKind(StrEnum):
    """The isolated runner selected for a compatibility case."""

    CONTRACT = "contract"
    E2E = "e2e"


class Lane(StrEnum):
    """Release policy lane for one explicit compatibility case."""

    REQUIRED = "required"
    PREVIEW = "preview"
    NIGHTLY = "nightly"


class SupportClaim(StrEnum):
    """Evidence strength asserted by the annotated test."""

    VERIFIED = "verified"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class CompatibilityProfile:
    """Shared client/runtime declaration for one independently selectable case."""

    id: str
    title_en: str
    title_ko: str
    client: str
    versions: Mapping[str, str]
    runtime_profile: str
    runtime_kind: str
    python_version: str
    lane: Lane
    execution: ExecutionKind
    expected_duration_minutes: int
    reference_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        _non_empty(self.id, "profile.id")
        _non_empty(self.title_en, "profile.title_en")
        _non_empty(self.title_ko, "profile.title_ko")
        _non_empty(self.client, "profile.client")
        _non_empty(self.runtime_profile, "profile.runtime_profile")
        if self.runtime_kind not in {"python", "emr", "glue"}:
            raise EvidenceValidationError(
                f"profile.runtime_kind must be python, emr, or glue: {self.runtime_kind!r}"
            )
        _non_empty(self.python_version, "profile.python_version")
        if (
            not isinstance(self.expected_duration_minutes, int)
            or isinstance(self.expected_duration_minutes, bool)
            or self.expected_duration_minutes <= 0
        ):
            raise EvidenceValidationError("profile.expected_duration_minutes must be positive")
        normalized_versions = _string_mapping(self.versions, "profile.versions")
        if not self.reference_urls or any(
            not value.startswith("https://") for value in self.reference_urls
        ):
            raise EvidenceValidationError("profile.reference_urls must contain HTTPS URLs")
        if len(self.reference_urls) != len(set(self.reference_urls)):
            raise EvidenceValidationError("profile.reference_urls must not repeat URLs")
        object.__setattr__(self, "versions", MappingProxyType(normalized_versions))

    def primitive(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe profile representation for pytest markers."""

        return {
            "id": self.id,
            "title_en": self.title_en,
            "title_ko": self.title_ko,
            "client": self.client,
            "versions": dict(sorted(self.versions.items())),
            "runtime_profile": self.runtime_profile,
            "runtime_kind": self.runtime_kind,
            "python_version": self.python_version,
            "lane": self.lane.value,
            "execution": self.execution.value,
            "expected_duration_minutes": self.expected_duration_minutes,
            "reference_urls": list(self.reference_urls),
        }

    @classmethod
    def from_primitive(cls, value: object) -> CompatibilityProfile:
        """Decode a marker profile while rejecting unknown fields before execution."""

        if not isinstance(value, Mapping):
            raise EvidenceValidationError("mystack_compatibility.profile must be a mapping")
        expected = {
            "id",
            "title_en",
            "title_ko",
            "client",
            "versions",
            "runtime_profile",
            "runtime_kind",
            "python_version",
            "lane",
            "execution",
            "expected_duration_minutes",
            "reference_urls",
        }
        unknown = sorted(set(value) - expected)
        missing = sorted(expected - set(value))
        if unknown or missing:
            raise EvidenceValidationError(
                f"mystack_compatibility.profile schema mismatch unknown={unknown} missing={missing}"
            )
        urls = value["reference_urls"]
        if not isinstance(urls, list | tuple) or any(not isinstance(url, str) for url in urls):
            raise EvidenceValidationError(
                "mystack_compatibility.profile.reference_urls must be strings"
            )
        try:
            lane = Lane(value["lane"])
            execution = ExecutionKind(value["execution"])
        except ValueError as error:
            raise EvidenceValidationError(
                "mystack_compatibility.profile has an unknown lane or execution kind"
            ) from error
        return cls(
            id=_as_text(value["id"], "profile.id"),
            title_en=_as_text(value["title_en"], "profile.title_en"),
            title_ko=_as_text(value["title_ko"], "profile.title_ko"),
            client=_as_text(value["client"], "profile.client"),
            versions=_string_mapping(value["versions"], "profile.versions"),
            runtime_profile=_as_text(value["runtime_profile"], "profile.runtime_profile"),
            runtime_kind=_as_text(value["runtime_kind"], "profile.runtime_kind"),
            python_version=_as_text(value["python_version"], "profile.python_version"),
            lane=lane,
            execution=execution,
            expected_duration_minutes=value["expected_duration_minutes"],
            reference_urls=tuple(urls),
        )


def compatibility_evidence(
    profile: CompatibilityProfile,
    *,
    scenario_ids: tuple[str, ...],
    operations: Mapping[str, tuple[str, ...]] | None = None,
    capabilities: tuple[str, ...] = (),
    support: SupportClaim = SupportClaim.VERIFIED,
) -> Callable[[_T], _T]:
    """Attach a typed, JSON-safe compatibility claim to one pytest test function.

    The collector merges test functions with the same profile ID into one CI case.  A test is
    deliberately responsible only for the scenarios and operations it proves; its profile owns
    the version/runtime/lane fields shared by the case.
    """

    scenarios = _string_sequence(scenario_ids, "scenario_ids")
    normalized_operations = {
        service: list(_string_sequence(names, f"operations.{service}"))
        for service, names in sorted((operations or {}).items())
    }
    if any(not service for service in normalized_operations):
        raise EvidenceValidationError("operations must use non-empty service names")
    normalized_capabilities = _string_sequence(capabilities, "capabilities", allow_empty=True)

    return pytest.mark.mystack_compatibility(
        profile=profile.primitive(),
        scenario_ids=list(scenarios),
        operations=normalized_operations,
        capabilities=list(normalized_capabilities),
        support=support.value,
    )


def marker_payload(value: Mapping[str, object]) -> dict[str, Any]:
    """Validate one raw pytest marker and return canonical primitive metadata."""

    expected = {"profile", "scenario_ids", "operations", "capabilities", "support"}
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown or missing:
        raise EvidenceValidationError(
            f"mystack_compatibility schema mismatch unknown={unknown} missing={missing}"
        )
    profile = CompatibilityProfile.from_primitive(value["profile"])
    try:
        support = SupportClaim(value["support"])
    except ValueError as error:
        raise EvidenceValidationError(
            f"mystack_compatibility.support is invalid: {value['support']!r}"
        ) from error
    scenarios = _string_sequence(value["scenario_ids"], "mystack_compatibility.scenario_ids")
    raw_operations = value["operations"]
    if not isinstance(raw_operations, Mapping):
        raise EvidenceValidationError("mystack_compatibility.operations must be a mapping")
    operations = {
        _as_text(service, "mystack_compatibility.operations service"): list(
            _string_sequence(names, f"mystack_compatibility.operations.{service}")
        )
        for service, names in sorted(raw_operations.items())
    }
    capabilities = _string_sequence(
        value["capabilities"], "mystack_compatibility.capabilities", allow_empty=True
    )
    return {
        "profile": profile.primitive(),
        "scenario_ids": list(scenarios),
        "operations": operations,
        "capabilities": list(capabilities),
        "support": support.value,
    }


def _as_text(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise EvidenceValidationError(f"{path} must be a string")
    _non_empty(value, path)
    return value


def _non_empty(value: str, path: str) -> None:
    if not value.strip():
        raise EvidenceValidationError(f"{path} must not be empty")


def _string_mapping(value: object, path: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise EvidenceValidationError(f"{path} must be a non-empty mapping")
    normalized = {
        _as_text(key, f"{path} key"): _as_text(item, f"{path}.{key}") for key, item in value.items()
    }
    return dict(sorted(normalized.items()))


def _string_sequence(value: object, path: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise EvidenceValidationError(f"{path} must be a list or tuple")
    normalized = tuple(_as_text(item, f"{path} item") for item in value)
    if not normalized and not allow_empty:
        raise EvidenceValidationError(f"{path} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise EvidenceValidationError(f"{path} must not repeat values")
    return normalized
