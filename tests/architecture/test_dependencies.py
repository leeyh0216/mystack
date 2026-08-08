"""Mutation-tested architecture contracts for every Python package boundary.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture_contract import (
    COMPOSITION_ROOT_MODULES,
    DEFAULT_BOUNDARIES,
    GENERATED_PYTHON_EXCLUSIONS,
    PackageBoundary,
    scan_repository,
)

ROOT = Path(__file__).parents[2]
SAMPLE = PackageBoundary(
    "sample",
    Path("sample/src/mystack/sample"),
    "mystack.sample",
    "layered",
)
OTHER = PackageBoundary(
    "other",
    Path("other/src/mystack/other"),
    "mystack.other",
    "layered",
)
SHARED = PackageBoundary(
    "shared",
    Path("shared/src/mystack/shared"),
    "mystack.shared",
    "shared",
)
PROXY = PackageBoundary(
    "proxy",
    Path("proxy/src/mystack/proxy"),
    "mystack.proxy",
    "proxy",
)


def _write_sources(root: Path, sources: dict[str, str]) -> None:
    for relative, content in sources.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_repository_architecture_is_clean() -> None:
    assert scan_repository(ROOT) == ()


def test_architecture_exceptions_are_explicit_and_minimal() -> None:
    assert COMPOSITION_ROOT_MODULES == frozenset({"mystack.emr.app", "mystack.glue.app"})
    assert GENERATED_PYTHON_EXCLUSIONS == ()
    assert {boundary.package for boundary in DEFAULT_BOUNDARIES} == {
        "mystack.aws_protocol",
        "mystack.proxy",
        "mystack.emr",
        "mystack.glue",
    }


@pytest.mark.parametrize(
    ("boundaries", "sources", "expected_rule"),
    (
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/domain/model.py": (
                    "from ..adapters.outbound import Repository\n"
                )
            },
            "outward-dependency",
            id="relative-domain-to-adapter",
        ),
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/adapters/outbound/runtime.py": (
                    "from ...config import Settings\n"
                )
            },
            "outward-dependency",
            id="adapter-to-bootstrap",
        ),
        pytest.param(
            (SAMPLE,),
            {"sample/src/mystack/sample/application/service.py": "from fastapi import Request\n"},
            "inner-transport-dependency",
            id="application-to-transport",
        ),
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/config.py": (
                    "from mystack.sample.adapters.outbound import Repository\n"
                )
            },
            "composition-only-adapter",
            id="adapter-import-outside-composition-root",
        ),
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/adapters/inbound/api.py": (
                    "from mystack.sample.adapters.outbound import Repository\n"
                )
            },
            "adapter-sibling-dependency",
            id="inbound-to-outbound-adapter",
        ),
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/adapters/inbound/api.py": (
                    "from mystack.sample.application.service import Application\n"
                )
            },
            "inbound-concrete-facade",
            id="inbound-to-concrete-application",
        ),
        pytest.param(
            (SHARED, SAMPLE),
            {"shared/src/mystack/shared/codec.py": ("from mystack.sample.domain import Entity\n")},
            "shared-service-dependency",
            id="shared-to-service",
        ),
        pytest.param(
            (PROXY, SAMPLE),
            {"proxy/src/mystack/proxy/routing.py": ("from mystack.sample.domain import Entity\n")},
            "proxy-service-dependency",
            id="proxy-to-service",
        ),
        pytest.param(
            (SAMPLE, OTHER),
            {
                "sample/src/mystack/sample/application/service.py": (
                    "from mystack.other.domain import Entity\n"
                )
            },
            "cross-service-dependency",
            id="service-to-service",
        ),
        pytest.param(
            (SAMPLE,),
            {
                "sample/src/mystack/sample/domain/a.py": "from . import b\n",
                "sample/src/mystack/sample/domain/b.py": "from . import a\n",
            },
            "service-import-cycle",
            id="relative-import-cycle",
        ),
    ),
)
def test_mutation_is_rejected_with_actionable_evidence(
    tmp_path: Path,
    boundaries: tuple[PackageBoundary, ...],
    sources: dict[str, str],
    expected_rule: str,
) -> None:
    _write_sources(tmp_path, sources)

    violations = scan_repository(tmp_path, boundaries)

    assert expected_rule in {violation.rule for violation in violations}
    rendered = "\n".join(violation.render(tmp_path) for violation in violations)
    for field in ("source=", "imported=", "rule=", "repair="):
        assert field in rendered
