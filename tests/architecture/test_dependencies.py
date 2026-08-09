"""Mutation-tested architecture contracts for every Python package boundary.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.quality.architecture_contract import (
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
GLUE = PackageBoundary(
    "glue",
    Path("glue/src/mystack/glue"),
    "mystack.glue",
    "layered",
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


def test_inbound_adapter_may_depend_on_application_protocols_and_policies(tmp_path: Path) -> None:
    _write_sources(
        tmp_path,
        {
            "sample/src/mystack/sample/adapters/inbound/api.py": (
                "from mystack.sample.application.policies import Policy\n"
                "from mystack.sample.application.use_cases import UseCase\n"
            ),
            "sample/src/mystack/sample/application/policies.py": "class Policy: pass\n",
            "sample/src/mystack/sample/application/use_cases.py": "class UseCase: pass\n",
        },
    )

    assert scan_repository(tmp_path, (SAMPLE,)) == ()


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
        pytest.param(
            (GLUE,),
            {"glue/src/mystack/glue/application/catalog.py": "import sqlite3\n"},
            "inner-sqlite-driver-dependency",
            id="application-to-sqlite-driver",
        ),
        pytest.param(
            (GLUE,),
            {
                "glue/src/mystack/glue/application/catalog.py": (
                    "def query(connection):\n    return connection.execute('SELECT 1')\n"
                )
            },
            "inner-sql-execution",
            id="application-to-literal-sql",
        ),
        pytest.param(
            (GLUE,),
            {
                "glue/src/mystack/glue/adapters/outbound/sqlite_catalog/store.py": (
                    "from mystack.glue.domain.errors import EntityNotFoundError\n"
                )
            },
            "sqlite-adapter-domain-error-dependency",
            id="sqlite-adapter-to-domain-error",
        ),
        pytest.param(
            (GLUE,),
            {
                "glue/src/mystack/glue/adapters/outbound/sqlite_catalog/store.py": (
                    "class EntityNotFoundError(Exception): pass\n"
                    "def load():\n    raise EntityNotFoundError()\n"
                )
            },
            "sqlite-adapter-domain-error-raise",
            id="sqlite-adapter-raises-domain-error",
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
