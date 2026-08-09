"""Contracts for matching source-build headers to the Glue image's active Python ABI.

Reference: https://docs.python.org/3/library/sysconfig.html
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[2]
DEPENDENCY_SCRIPT = ROOT / "glue/scripts/install_python_build_dependencies.py"


def _dependency_module() -> ModuleType:
    name = "mystack_glue_sqlite_build_dependencies_test"
    spec = importlib.util.spec_from_file_location(name, DEPENDENCY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_dependencies_are_derived_from_the_active_python_abi_not_generic_aliases() -> None:
    dependency_module = _dependency_module()

    dependencies = dependency_module.resolve_dependencies(
        executable="/usr/bin/python3",
        major=3,
        minor=11,
        include_directory=Path("/usr/include/python3.11"),
    )

    assert dependencies.abi == "3.11"
    assert dependencies.header == Path("/usr/include/python3.11/Python.h")
    assert dependencies.packages == (
        "gcc",
        "make",
        "python3.11-devel",
        "python3.11-setuptools",
    )
    assert "python3-devel" not in dependencies.packages


def test_install_requires_matching_headers_and_logs_the_resolved_abi(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    dependency_module = _dependency_module()
    include_directory = tmp_path / "include"
    include_directory.mkdir()
    (include_directory / "Python.h").touch()
    dependencies = dependency_module.resolve_dependencies(
        executable="/usr/bin/python3",
        major=3,
        minor=12,
        include_directory=include_directory,
    )
    commands: list[list[str]] = []

    def runner(command: list[str], *, check: bool) -> subprocess.CompletedProcess[object]:
        assert check is True
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(dependency_module.importlib.util, "find_spec", lambda name: object())

    dependency_module.install(dependencies, runner=runner)

    assert commands == [
        [
            "dnf",
            "install",
            "--assumeyes",
            "--setopt=install_weak_deps=False",
            "gcc",
            "make",
            "python3.12-devel",
            "python3.12-setuptools",
        ]
    ]
    output = capsys.readouterr().out
    assert '"event": "glue.sqlite.build.python_dependencies.before"' in output
    assert '"python_abi": "3.12"' in output


def test_glue_dockerfile_uses_the_active_abi_dependency_resolver() -> None:
    dockerfile = (ROOT / "glue/Dockerfile").read_text(encoding="utf-8")

    assert "install_python_build_dependencies.py" in dockerfile
    assert "python3-devel" not in dockerfile
