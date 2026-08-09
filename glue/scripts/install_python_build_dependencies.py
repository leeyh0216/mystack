#!/usr/bin/env python3
"""Install source-build dependencies for the active AWS Glue Python ABI.

The Glue base image can expose a newer ``python3`` than Amazon Linux's generic ``python3-devel``
package.  Resolve the development package from the interpreter actually executing this script so
the private pysqlite3 extension always receives matching ``Python.h`` headers.

References:
- https://docs.python.org/3/library/sysconfig.html
- https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class BuildDependencyError(RuntimeError):
    """The Glue base image cannot supply build dependencies for its active Python ABI."""


class CommandRunner(Protocol):
    """Minimal subprocess boundary kept injectable for focused contract tests."""

    def __call__(self, args: list[str], *, check: bool) -> subprocess.CompletedProcess[object]: ...


@dataclass(frozen=True, slots=True)
class PythonBuildDependencies:
    """Exact packages and header location derived from one interpreter ABI."""

    executable: str
    abi: str
    include_directory: Path
    packages: tuple[str, ...]

    @property
    def header(self) -> Path:
        return self.include_directory / "Python.h"


def emit(event: str, **fields: object) -> None:
    """Log build boundaries without configuration values or source URLs."""
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def resolve_dependencies(
    *,
    executable: str,
    major: int,
    minor: int,
    include_directory: Path,
) -> PythonBuildDependencies:
    """Return version-specific RPM names instead of Amazon Linux's generic Python aliases."""
    if major < 3 or minor < 0:
        raise BuildDependencyError(f"Unsupported active Python ABI: {major}.{minor}")
    abi = f"{major}.{minor}"
    return PythonBuildDependencies(
        executable=executable,
        abi=abi,
        include_directory=include_directory,
        packages=(
            "gcc",
            "make",
            f"python{abi}-devel",
            f"python{abi}-setuptools",
        ),
    )


def active_dependencies() -> PythonBuildDependencies:
    """Inspect the interpreter used by Dockerfile's ``python3`` invocation."""
    include_directory = sysconfig.get_path("include")
    if not include_directory:
        raise BuildDependencyError(
            "Active Python did not report an include directory through sysconfig."
        )
    return resolve_dependencies(
        executable=sys.executable,
        major=sys.version_info.major,
        minor=sys.version_info.minor,
        include_directory=Path(include_directory),
    )


def install(
    dependencies: PythonBuildDependencies,
    *,
    runner: CommandRunner = subprocess.run,
) -> None:
    """Install and verify dependencies; do not substitute a mismatched header package."""
    emit(
        "glue.sqlite.build.python_dependencies.before",
        executable=dependencies.executable,
        python_abi=dependencies.abi,
        header=str(dependencies.header),
        packages=list(dependencies.packages),
    )
    try:
        runner(
            [
                "dnf",
                "install",
                "--assumeyes",
                "--setopt=install_weak_deps=False",
                *dependencies.packages,
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BuildDependencyError(
            "Unable to install development headers for the active Python "
            f"ABI {dependencies.abi}. The Glue base must provide "
            f"{dependencies.packages[2]!r}; do not replace it with a generic python3-devel package."
        ) from error
    if not dependencies.header.is_file():
        raise BuildDependencyError(
            "The installed development package does not provide the active Python header at "
            f"{dependencies.header}."
        )
    if importlib.util.find_spec("setuptools") is None:
        raise BuildDependencyError(
            "The installed active-Python setuptools package is unavailable to the SQLite builder."
        )
    emit(
        "glue.sqlite.build.python_dependencies.after",
        python_abi=dependencies.abi,
        header=str(dependencies.header),
    )


def main() -> int:
    """Install dependencies for this executable's ABI at the Docker build boundary."""
    install(active_dependencies())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
