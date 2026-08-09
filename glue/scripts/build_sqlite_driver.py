#!/usr/bin/env python3
"""Build Mystack's private SQLite DB-API module from checksum-verified source artifacts.

The Python extension embeds SQLite's official amalgamation rather than linking the AWS Glue image's
system SQLite library. The resulting package is copied only into Mystack's virtual environment.

References:
- https://www.sqlite.org/download.html
- https://github.com/coleifer/pysqlite3/blob/master/setup.py
- https://docs.python.org/3/library/urllib.request.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){2,3}")
_TOP_LEVEL_FIELDS = frozenset({"schema_version", "sqlite", "driver", "official_sources"})
_SQLITE_FIELDS = frozenset({"version", "minimum_wal_version", "amalgamation"})
_AMALGAMATION_FIELDS = frozenset({"url", "sha3_256"})
_DRIVER_FIELDS = frozenset({"distribution", "module", "version", "source"})
_DRIVER_SOURCE_FIELDS = frozenset({"url", "sha256"})
_MINIMUM_SAFE_WAL_VERSION = (3, 51, 3)


class BuildError(RuntimeError):
    """A source provenance, safe extraction, or extension-build failure."""


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    url: str
    filename: str
    digest_algorithm: str
    digest: str


@dataclass(frozen=True, slots=True)
class SQLiteDriverBuildSpec:
    sqlite_version: str
    minimum_wal_version: str
    amalgamation: SourceArtifact
    driver_distribution: str
    driver_module: str
    driver_version: str
    driver_source: SourceArtifact


def emit(event: str, **fields: object) -> None:
    """Emit build boundaries without source URLs, credentials, or query strings."""
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def load_spec(path: Path) -> SQLiteDriverBuildSpec:
    """Read the strict file-driven source pin without accepting unreviewed fields."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BuildError(
            "SQLite runtime build configuration is unavailable or invalid JSON"
        ) from error
    document = _mapping(raw, "root")
    _exact_fields(document, _TOP_LEVEL_FIELDS, "root")
    if document.get("schema_version") != 1:
        raise BuildError("Unsupported SQLite runtime build configuration schema_version")
    sqlite = _mapping(document["sqlite"], "sqlite")
    _exact_fields(sqlite, _SQLITE_FIELDS, "sqlite")
    amalgamation = _mapping(sqlite["amalgamation"], "sqlite.amalgamation")
    _exact_fields(amalgamation, _AMALGAMATION_FIELDS, "sqlite.amalgamation")
    driver = _mapping(document["driver"], "driver")
    _exact_fields(driver, _DRIVER_FIELDS, "driver")
    driver_source = _mapping(driver["source"], "driver.source")
    _exact_fields(driver_source, _DRIVER_SOURCE_FIELDS, "driver.source")

    sqlite_version = _version(sqlite["version"], "sqlite.version")
    minimum_wal_version = _version(sqlite["minimum_wal_version"], "sqlite.minimum_wal_version")
    if _version_parts(minimum_wal_version) < _MINIMUM_SAFE_WAL_VERSION:
        raise BuildError("sqlite.minimum_wal_version cannot be below 3.51.3")
    if _version_parts(sqlite_version) < _version_parts(minimum_wal_version):
        raise BuildError("sqlite.version must be at least sqlite.minimum_wal_version")
    distribution = _non_empty_string(driver["distribution"], "driver.distribution")
    module = _non_empty_string(driver["module"], "driver.module")
    driver_version = _version(driver["version"], "driver.version")
    return SQLiteDriverBuildSpec(
        sqlite_version=sqlite_version,
        minimum_wal_version=minimum_wal_version,
        amalgamation=_artifact(
            amalgamation["url"],
            amalgamation["sha3_256"],
            "sha3_256",
            "sqlite.amalgamation",
        ),
        driver_distribution=distribution,
        driver_module=module,
        driver_version=driver_version,
        driver_source=_artifact(
            driver_source["url"],
            driver_source["sha256"],
            "sha256",
            "driver.source",
        ),
    )


def build(spec: SQLiteDriverBuildSpec, output: Path) -> dict[str, object]:
    """Compile a private `pysqlite3` package from the verified pinned sources."""
    if output.exists() and any(output.iterdir()):
        raise BuildError("SQLite driver output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    emit(
        "glue.sqlite.build.before",
        sqlite_version=spec.sqlite_version,
        minimum_wal_version=spec.minimum_wal_version,
        driver_distribution=spec.driver_distribution,
        driver_version=spec.driver_version,
    )
    with tempfile.TemporaryDirectory(prefix="mystack-sqlite-build-") as raw_workspace:
        workspace = Path(raw_workspace)
        amalgamation_archive = workspace / spec.amalgamation.filename
        driver_archive = workspace / spec.driver_source.filename
        _download_verified(spec.amalgamation, amalgamation_archive)
        _download_verified(spec.driver_source, driver_archive)

        sqlite_root = workspace / "sqlite"
        driver_root = workspace / "driver"
        _extract_zip(amalgamation_archive, sqlite_root)
        _extract_tar(driver_archive, driver_root)
        sqlite_source = _single_directory(sqlite_root, "SQLite amalgamation")
        driver_source = _single_directory(driver_root, "pysqlite3 source")
        _prepare_pysqlite_source(sqlite_source, driver_source)
        _compile_extension(driver_source)
        _copy_package(driver_source, output)
        _verify_built_driver(output, spec)
        manifest = _manifest(spec)
        (output / "runtime-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    emit(
        "glue.sqlite.build.after",
        sqlite_version=spec.sqlite_version,
        driver_module=spec.driver_module,
        architecture=platform.machine(),
    )
    return manifest


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BuildError(f"SQLite runtime build configuration {path} must be an object")
    return value


def _exact_fields(value: dict[str, Any], expected: frozenset[str], path: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown or missing:
        raise BuildError(
            f"SQLite runtime build configuration {path} has unknown={unknown} missing={missing}"
        )


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildError(f"SQLite runtime build configuration {path} must be a non-empty string")
    return value


def _version(value: object, path: str) -> str:
    candidate = _non_empty_string(value, path)
    if not _VERSION_PATTERN.fullmatch(candidate):
        raise BuildError(f"SQLite runtime build configuration {path} must be a SQLite version")
    return candidate


def _version_parts(value: str) -> tuple[int, ...]:
    return tuple(int(component) for component in value.split("."))


def _artifact(value: object, digest: object, algorithm: str, path: str) -> SourceArtifact:
    url = _non_empty_string(value, f"{path}.url")
    filename = _safe_source_filename(url, path)
    expected_digest = _non_empty_string(digest, f"{path}.{algorithm}")
    if not _DIGEST_PATTERN.fullmatch(expected_digest):
        raise BuildError(
            f"SQLite runtime build configuration {path}.{algorithm} must be a 64-character "
            "lowercase hexadecimal digest"
        )
    return SourceArtifact(url, filename, algorithm, expected_digest)


def _safe_source_filename(url: str, path: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BuildError(f"SQLite runtime build configuration {path}.url must be a clean HTTPS URL")
    source_path = PurePosixPath(parsed.path)
    if ".." in source_path.parts or "\\" in parsed.path:
        raise BuildError(f"SQLite runtime build configuration {path}.url has an unsafe source path")
    filename = source_path.name
    if not filename:
        raise BuildError(f"SQLite runtime build configuration {path}.url must name an artifact")
    return filename


def _download_verified(artifact: SourceArtifact, destination: Path) -> None:
    emit(
        "glue.sqlite.build.download.before",
        source_name=artifact.filename,
        digest_algorithm=artifact.digest_algorithm,
    )
    digest = hashlib.new(artifact.digest_algorithm)
    request = urllib.request.Request(
        artifact.url,
        headers={"User-Agent": "mystack-sqlite-runtime-builder/1"},
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            destination.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                target.write(chunk)
    except OSError as error:
        raise BuildError(
            f"Failed to download verified SQLite source artifact: {artifact.filename}"
        ) from error
    actual = digest.hexdigest()
    if actual != artifact.digest:
        destination.unlink(missing_ok=True)
        raise BuildError(f"Checksum mismatch for SQLite source artifact: {artifact.filename}")
    emit(
        "glue.sqlite.build.download.after",
        source_name=artifact.filename,
        digest_algorithm=artifact.digest_algorithm,
    )


def _extract_zip(archive: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                target = _safe_archive_target(destination, member.filename)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_stream, target.open("wb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)
    except (OSError, zipfile.BadZipFile) as error:
        raise BuildError("Failed to safely extract SQLite amalgamation source") from error


def _extract_tar(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, mode="r:gz") as source:
            for member in source.getmembers():
                target = _safe_archive_target(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isreg():
                    raise BuildError("pysqlite3 source archive contains a non-regular file")
                input_stream = source.extractfile(member)
                if input_stream is None:
                    raise BuildError("pysqlite3 source archive member cannot be read")
                target.parent.mkdir(parents=True, exist_ok=True)
                with input_stream, target.open("wb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream)
    except (OSError, tarfile.TarError) as error:
        raise BuildError("Failed to safely extract pysqlite3 source") from error


def _safe_archive_target(destination: Path, member_name: str) -> Path:
    path = PurePosixPath(member_name)
    if path.is_absolute() or ".." in path.parts or "\\" in member_name:
        raise BuildError("SQLite source archive contains an unsafe member path")
    target = destination.joinpath(*path.parts)
    resolved_destination = destination.resolve()
    if not target.resolve().is_relative_to(resolved_destination):
        raise BuildError("SQLite source archive member escapes its extraction directory")
    return target


def _single_directory(root: Path, description: str) -> Path:
    children = [child for child in root.iterdir() if child.is_dir()]
    if len(children) != 1:
        raise BuildError(f"{description} must extract to exactly one top-level directory")
    return children[0]


def _prepare_pysqlite_source(sqlite_source: Path, driver_source: Path) -> None:
    for name in ("sqlite3.c", "sqlite3.h", "sqlite3ext.h"):
        source = sqlite_source / name
        if not source.is_file():
            if name == "sqlite3ext.h":
                continue
            raise BuildError(f"SQLite amalgamation is missing {name}")
        shutil.copy2(source, driver_source / name)


def _compile_extension(driver_source: Path) -> None:
    emit("glue.sqlite.build.compile.before", driver_source=driver_source.name)
    try:
        subprocess.run(
            [sys.executable, "setup.py", "build_ext", "--inplace"],
            cwd=driver_source,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BuildError("Failed to compile the private pysqlite3 extension") from error
    if not any((driver_source / "pysqlite3").glob("_sqlite3*.so")):
        raise BuildError("Private pysqlite3 extension build did not produce an importable module")
    emit("glue.sqlite.build.compile.after", driver_source=driver_source.name)


def _copy_package(driver_source: Path, output: Path) -> None:
    package = driver_source / "pysqlite3"
    license_file = driver_source / "LICENSE"
    shutil.copytree(package, output / "pysqlite3")
    licenses = output / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(license_file, licenses / "pysqlite3-LICENSE")


def _verify_built_driver(output: Path, spec: SQLiteDriverBuildSpec) -> None:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(output) if not existing else f"{output}{os.pathsep}{existing}"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pysqlite3; print(pysqlite3.sqlite_version)",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BuildError("Private pysqlite3 extension failed its import probe") from error
    actual_version = completed.stdout.strip()
    if actual_version != spec.sqlite_version:
        raise BuildError(
            "Private pysqlite3 extension did not embed the configured SQLite version: "
            f"expected {spec.sqlite_version}, got {actual_version or '<empty>'}"
        )


def _manifest(spec: SQLiteDriverBuildSpec) -> dict[str, object]:
    return {
        "schema_version": 1,
        "architecture": platform.machine(),
        "sqlite": {
            "version": spec.sqlite_version,
            "minimum_wal_version": spec.minimum_wal_version,
            "amalgamation_sha3_256": spec.amalgamation.digest,
        },
        "driver": {
            "distribution": spec.driver_distribution,
            "module": spec.driver_module,
            "version": spec.driver_version,
            "source_sha256": spec.driver_source.digest,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec = load_spec(args.config)
    build(spec, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
