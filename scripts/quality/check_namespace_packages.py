"""Verify that independently built wheels safely compose a PEP 420 namespace.

References:
- https://docs.python.org/3/reference/import.html#namespace-packages
- https://docs.python.org/3/library/venv.html
- https://docs.astral.sh/uv/concepts/build-backend/#namespace-packages
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Distribution:
    project_name: str
    version: str
    module_name: str
    wheel: Path


def _event(name: str, **fields: object) -> None:
    print(json.dumps({"event": name, **fields}, sort_keys=True), flush=True)


def _workspace_distributions(
    workspace_root: Path,
    dist_dir: Path,
) -> tuple[Distribution, ...]:
    root = tomllib.loads((workspace_root / "pyproject.toml").read_text(encoding="utf-8"))
    distributions: list[Distribution] = []
    for member in root["tool"]["uv"]["workspace"]["members"]:
        document = tomllib.loads(
            (workspace_root / member / "pyproject.toml").read_text(encoding="utf-8")
        )
        project = document["project"]
        module_name = document["tool"]["uv"]["build-backend"]["module-name"]
        prefix = str(project["name"]).replace("-", "_")
        matches = tuple(sorted(dist_dir.glob(f"{prefix}-{project['version']}-*.whl")))
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one wheel for {project['name']} {project['version']}, found {matches}"
            )
        distributions.append(
            Distribution(
                project_name=str(project["name"]),
                version=str(project["version"]),
                module_name=str(module_name),
                wheel=matches[0],
            )
        )
    return tuple(distributions)


def _inspect_wheels(distributions: tuple[Distribution, ...]) -> None:
    for distribution in distributions:
        expected = f"{distribution.module_name.replace('.', '/')}/__init__.py"
        with zipfile.ZipFile(distribution.wheel) as archive:
            members = set(archive.namelist())
        if "mystack/__init__.py" in members:
            raise RuntimeError(f"{distribution.wheel.name} owns the PEP 420 namespace root")
        if expected not in members:
            raise RuntimeError(f"{distribution.wheel.name} does not contain {expected}")
        _event(
            "namespace.wheel.inspect.after",
            distribution=distribution.project_name,
            module=distribution.module_name,
            wheel=distribution.wheel.name,
        )


def _run(command: list[str], timeout_seconds: float) -> None:
    _event("namespace.process.before", executable=command[0], arguments=command[1:3])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        _event(
            "namespace.process.failed",
            executable=command[0],
            return_code=completed.returncode,
            stderr=completed.stderr[-4000:],
            fix_hint="Inspect wheel module-name settings and the implicit mystack namespace root.",
        )
        raise RuntimeError(f"namespace smoke subprocess failed: {command[0]}")
    _event("namespace.process.after", executable=command[0], return_code=0)


def verify(workspace_root: Path, dist_dir: Path, timeout_seconds: float) -> None:
    distributions = _workspace_distributions(workspace_root, dist_dir)
    _inspect_wheels(distributions)
    modules = [distribution.module_name for distribution in distributions]
    smoke = (
        "import importlib.util, json, mystack; "
        "modules=json.loads(" + repr(json.dumps(modules)) + "); "
        "assert mystack.__file__ is None; "
        "assert all(importlib.util.find_spec(name) is not None for name in modules)"
    )
    with tempfile.TemporaryDirectory(prefix="mystack-namespace-") as temporary:
        environment = Path(temporary) / "venv"
        _run([sys.executable, "-m", "venv", str(environment)], timeout_seconds)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--no-deps",
                *(str(distribution.wheel) for distribution in distributions),
            ],
            timeout_seconds,
        )
        _run([str(python), "-c", smoke], timeout_seconds)
    _event("namespace.contract.clean", distributions=len(distributions), modules=modules)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path(__file__).parents[2])
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    arguments = parser.parse_args()
    verify(
        arguments.workspace_root.resolve(),
        arguments.dist_dir.resolve(),
        arguments.timeout_seconds,
    )


if __name__ == "__main__":
    main()
