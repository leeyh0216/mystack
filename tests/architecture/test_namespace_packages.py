"""Verify the shared PEP 420 namespace contract.

References:
- https://docs.python.org/3/reference/import.html#namespace-packages
- https://docs.astral.sh/uv/concepts/build-backend/#namespace-packages
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]
PROJECTS = ("shared", "proxy", "emr", "glue")


def test_namespace_root_has_no_init_module() -> None:
    for project in PROJECTS:
        assert not (ROOT / project / "src" / "mystack" / "__init__.py").exists()


def test_each_distribution_declares_its_dotted_uv_module() -> None:
    modules: set[str] = set()
    for project in PROJECTS:
        document = tomllib.loads((ROOT / project / "pyproject.toml").read_text(encoding="utf-8"))
        module_name = document["tool"]["uv"]["build-backend"]["module-name"]
        assert module_name.startswith("mystack.")
        assert (ROOT / project / "src" / Path(*module_name.split("."))).is_dir()
        modules.add(module_name)
    assert len(modules) == len(PROJECTS)


def test_workspace_combines_all_distributions_under_one_namespace() -> None:
    namespace = importlib.import_module("mystack")
    assert namespace.__file__ is None
    for module_name in (
        "mystack.aws_protocol",
        "mystack.proxy",
        "mystack.emr",
        "mystack.glue",
    ):
        assert importlib.util.find_spec(module_name) is not None
