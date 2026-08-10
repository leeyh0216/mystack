#!/usr/bin/env python3
"""Manage the repository's stable version authority without publishing anything.

Official references:
- https://semver.org/
- https://packaging.python.org/en/latest/specifications/version-specifiers/
- https://docs.npmjs.com/cli/commands/npm-version
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config/release/version-files.json"
LOGGER = logging.getLogger("mystack.version")
_SEMVER_CORE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


class VersionError(ValueError):
    """The version request cannot be completed deterministically."""


@dataclass(frozen=True, order=True, slots=True)
class StableVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> StableVersion:
        match = _SEMVER_CORE.fullmatch(value.strip())
        if match is None:
            raise VersionError(f"invalid stable version {value!r}; fix_hint=use-semver-core-X.Y.Z")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def tag(self) -> str:
        return f"v{self}"

    def bump(self, part: str) -> StableVersion:
        if part == "major":
            return StableVersion(self.major + 1, 0, 0)
        if part == "minor":
            return StableVersion(self.major, self.minor + 1, 0)
        if part == "patch":
            return StableVersion(self.major, self.minor, self.patch + 1)
        raise VersionError(f"unknown bump part {part!r}; fix_hint=use-major-minor-or-patch")

    def snapshot(self, *, run_number: int, commit_sha: str) -> ResolvedVersion:
        if run_number <= 0:
            raise VersionError("snapshot run number must be positive")
        if _COMMIT_SHA.fullmatch(commit_sha) is None:
            raise VersionError("snapshot commit SHA must contain 7 to 40 hexadecimal characters")
        short_sha = commit_sha.lower()[:8]
        return ResolvedVersion(
            stable=self,
            channel="snapshot",
            oci_tag=f"v{self}-snapshot.{run_number}.g{short_sha}",
            python_version=f"{self}.dev{run_number}+g{short_sha}",
        )

    def release(self) -> ResolvedVersion:
        return ResolvedVersion(
            stable=self,
            channel="stable",
            oci_tag=self.tag,
            python_version=str(self),
        )


@dataclass(frozen=True, slots=True)
class ResolvedVersion:
    stable: StableVersion
    channel: str
    oci_tag: str
    python_version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "stable_version": str(self.stable),
            "channel": self.channel,
            "oci_tag": self.oci_tag,
            "python_version": self.python_version,
        }


@dataclass(frozen=True, slots=True)
class VersionConfiguration:
    root: Path
    authority: Path
    command_timeout_seconds: float
    files: tuple[dict[str, Any], ...]

    TOP_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "authority",
            "command_timeout_seconds",
            "files",
            "official_sources",
        }
    )

    @classmethod
    def load(cls, path: Path, *, root: Path = ROOT) -> VersionConfiguration:
        LOGGER.info("event=version.config.load.before path=%s", path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise VersionError(f"cannot load version config path={path}: {error}") from error
        if not isinstance(document, dict) or set(document) != cls.TOP_FIELDS:
            raise VersionError("version config has unknown or missing top-level fields")
        if document["schema_version"] != 1:
            raise VersionError("version config schema_version must be 1")
        sources = document["official_sources"]
        if (
            not isinstance(sources, list)
            or not sources
            or any(
                not isinstance(source, str) or not source.startswith("https://")
                for source in sources
            )
        ):
            raise VersionError("version config official_sources must be non-empty HTTPS URLs")
        raw_files = document["files"]
        if (
            not isinstance(raw_files, list)
            or not raw_files
            or any(not isinstance(value, dict) for value in raw_files)
        ):
            raise VersionError("version config files must be a non-empty list of objects")
        authority = _safe_repository_path(root, document["authority"], "authority")
        timeout = float(document["command_timeout_seconds"])
        if timeout <= 0:
            raise VersionError("version command timeout must be positive")
        configuration = cls(root.resolve(), authority, timeout, tuple(raw_files))
        VersionSynchronizer(configuration).validate_configuration()
        LOGGER.info(
            "event=version.config.load.after path=%s managed_files=%d",
            path,
            len(raw_files),
        )
        return configuration


class VersionFile:
    """Render one configured file for a stable version."""

    def __init__(self, root: Path, spec: Mapping[str, Any]) -> None:
        self.path = _safe_repository_path(root, spec.get("path"), "files.path")
        self.spec = spec

    def render(self, version: StableVersion) -> str:
        raise NotImplementedError

    def _read(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as error:
            raise VersionError(
                f"cannot read managed version file path={self.path}: {error}"
            ) from error

    def _require_fields(self, fields: set[str]) -> None:
        unknown = sorted(set(self.spec) - fields)
        missing = sorted(fields - set(self.spec))
        if unknown or missing:
            raise VersionError(
                f"version file schema mismatch path={self.path} unknown={unknown} missing={missing}"
            )


class TomlProjectVersionFile(VersionFile):
    _PATTERN = re.compile(r'(?m)^version = "[^"]+"$')

    def render(self, version: StableVersion) -> str:
        self._require_fields({"path", "kind"})
        current = self._read()
        rendered, count = self._PATTERN.subn(f'version = "{version}"', current, count=1)
        if count != 1:
            raise VersionError(f"expected one project version path={self.path} actual={count}")
        return rendered


class UvLockVersionFile(VersionFile):
    def render(self, version: StableVersion) -> str:
        self._require_fields({"path", "kind", "packages"})
        current = self._read()
        packages = _unique_strings(self.spec.get("packages"), f"{self.path}.packages")
        for package in packages:
            pattern = re.compile(
                rf'(?m)(^\[\[package\]\]\nname = "{re.escape(package)}"\nversion = ")[^"]+("$)'
            )
            current, count = pattern.subn(rf"\g<1>{version}\g<2>", current)
            if count != 1:
                raise VersionError(
                    f"expected one uv lock package version path={self.path} "
                    f"package={package} actual={count}"
                )
        return current


class JsonVersionFile(VersionFile):
    def render(self, version: StableVersion) -> str:
        self._require_fields({"path", "kind", "fields"})
        try:
            document = json.loads(self._read())
        except json.JSONDecodeError as error:
            raise VersionError(f"invalid managed JSON path={self.path}: {error}") from error
        fields = self.spec.get("fields")
        if not isinstance(fields, list) or not fields:
            raise VersionError(f"JSON version fields must be non-empty path={self.path}")
        for raw_field in fields:
            field = _json_field_path(raw_field, f"{self.path}.fields")
            target = document
            for member in field[:-1]:
                if not isinstance(target, dict) or member not in target:
                    raise VersionError(f"missing JSON version field path={self.path} field={field}")
                target = target[member]
            if not isinstance(target, dict) or field[-1] not in target:
                raise VersionError(f"missing JSON version field path={self.path} field={field}")
            target[field[-1]] = str(version)
        return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


class RegexVersionFile(VersionFile):
    def render(self, version: StableVersion) -> str:
        self._require_fields({"path", "kind", "pattern", "replacement", "expected_matches"})
        try:
            pattern = re.compile(str(self.spec["pattern"]))
        except re.error as error:
            raise VersionError(f"invalid version regex path={self.path}: {error}") from error
        expected = self.spec["expected_matches"]
        if not isinstance(expected, int) or isinstance(expected, bool) or expected <= 0:
            raise VersionError(f"regex expected_matches must be positive path={self.path}")
        replacement = str(self.spec["replacement"]).format(version=version)
        rendered, count = pattern.subn(replacement, self._read())
        if count != expected:
            raise VersionError(
                f"version marker count drift path={self.path} expected={expected} actual={count} "
                "fix_hint=update-config-version-files"
            )
        return rendered


class VersionSynchronizer:
    """Own configured version-file drift detection and atomic updates."""

    KINDS: ClassVar[dict[str, type[VersionFile]]] = {
        "toml-project": TomlProjectVersionFile,
        "uv-lock": UvLockVersionFile,
        "json": JsonVersionFile,
        "regex": RegexVersionFile,
    }

    def __init__(self, configuration: VersionConfiguration) -> None:
        self._configuration = configuration

    def validate_configuration(self) -> None:
        seen: set[Path] = set()
        for spec in self._configuration.files:
            kind = spec.get("kind")
            adapter = self.KINDS.get(str(kind))
            if adapter is None:
                raise VersionError(f"unknown version file kind {kind!r}")
            file = adapter(self._configuration.root, spec)
            if file.path in seen:
                raise VersionError(f"duplicate managed version file path={file.path}")
            seen.add(file.path)
        if self._configuration.authority in seen:
            raise VersionError("VERSION authority must not also be a managed derivative")

    def authority(self) -> StableVersion:
        try:
            value = self._configuration.authority.read_text(encoding="utf-8")
        except OSError as error:
            raise VersionError(f"cannot read version authority: {error}") from error
        if not value.endswith("\n") or value.count("\n") != 1:
            raise VersionError("VERSION must contain one stable SemVer core followed by a newline")
        return StableVersion.parse(value.removesuffix("\n"))

    def expected(self, version: StableVersion) -> dict[Path, str]:
        values: dict[Path, str] = {
            self._configuration.authority: f"{version}\n",
        }
        for spec in self._configuration.files:
            adapter = self.KINDS[str(spec["kind"])](self._configuration.root, spec)
            values[adapter.path] = adapter.render(version)
        return values

    def drift(self, version: StableVersion | None = None) -> dict[Path, tuple[str, str]]:
        version = version or self.authority()
        drift: dict[Path, tuple[str, str]] = {}
        for path, expected in self.expected(version).items():
            try:
                current = path.read_text(encoding="utf-8")
            except OSError as error:
                raise VersionError(
                    f"cannot inspect managed version file path={path}: {error}"
                ) from error
            if current != expected:
                drift[path] = (current, expected)
        return drift

    def check(self) -> StableVersion:
        version = self.authority()
        drift = self.drift(version)
        if drift:
            paths = ",".join(str(path.relative_to(self._configuration.root)) for path in drift)
            raise VersionError(
                f"version-bearing file drift paths={paths}; fix_hint=run-make-version-check-or-set"
            )
        LOGGER.info(
            "event=version.drift.check.after version=%s files=%d",
            version,
            len(self.expected(version)),
        )
        return version

    def update(self, version: StableVersion, *, dry_run: bool) -> str:
        drift = self.drift(version)
        diff = self._diff(drift)
        LOGGER.info(
            "event=version.update.before version=%s dry_run=%s changed_files=%d side_effect=%s",
            version,
            str(dry_run).lower(),
            len(drift),
            str(not dry_run).lower(),
        )
        if not dry_run:
            for path, (_, expected) in drift.items():
                _atomic_write(path, expected)
        LOGGER.info(
            "event=version.update.after version=%s dry_run=%s changed_files=%d side_effect=%s",
            version,
            str(dry_run).lower(),
            len(drift),
            str(not dry_run).lower(),
        )
        return diff

    def _diff(self, drift: Mapping[Path, tuple[str, str]]) -> str:
        lines: list[str] = []
        for path in sorted(drift):
            current, expected = drift[path]
            relative = path.relative_to(self._configuration.root)
            lines.extend(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
        return "".join(lines)


class GitVersionHistory:
    """Read-only Git/GitHub checks used before a main release side effect."""

    def __init__(self, root: Path, *, timeout_seconds: float) -> None:
        self._root = root
        self._timeout_seconds = timeout_seconds

    def ensure_clean(self) -> None:
        output = self._run(("git", "status", "--porcelain", "--untracked-files=all"))
        if output.strip():
            raise VersionError("working tree is dirty; fix_hint=commit-stash-or-use-allow-dirty")

    def version_at(self, reference: str, authority: Path) -> StableVersion | None:
        relative = authority.relative_to(self._root)
        process = self._run_process(("git", "show", f"{reference}:{relative}"), check=False)
        if process.returncode != 0:
            return None
        return StableVersion.parse(process.stdout.strip())

    def stable_tags(self) -> tuple[StableVersion, ...]:
        values = []
        for tag in self._run(("git", "tag", "--list", "v*")).splitlines():
            try:
                values.append(StableVersion.parse(tag.removeprefix("v")))
            except VersionError:
                continue
        return tuple(sorted(set(values)))

    def tag_commit(self, tag: str) -> str | None:
        process = self._run_process(("git", "rev-list", "-n", "1", tag), check=False)
        if process.returncode != 0:
            return None
        return process.stdout.strip().lower()

    def github_release_tags(self, repository: str) -> tuple[StableVersion, ...]:
        output = self._run(
            (
                "gh",
                "release",
                "list",
                "--repo",
                repository,
                "--limit",
                "1000",
                "--json",
                "tagName",
                "--jq",
                ".[].tagName",
            )
        )
        values = []
        for tag in output.splitlines():
            try:
                values.append(StableVersion.parse(tag.removeprefix("v")))
            except VersionError:
                continue
        return tuple(sorted(set(values)))

    def _run(self, command: Sequence[str]) -> str:
        return self._run_process(command, check=True).stdout

    def _run_process(
        self, command: Sequence[str], *, check: bool
    ) -> subprocess.CompletedProcess[str]:
        LOGGER.info(
            "event=version.command.before executable=%s arg_count=%d", command[0], len(command) - 1
        )
        try:
            process = subprocess.run(
                command,
                cwd=self._root,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VersionError(
                f"version command failed executable={command[0]}: {error}"
            ) from error
        LOGGER.info(
            "event=version.command.after executable=%s returncode=%d",
            command[0],
            process.returncode,
        )
        if check and process.returncode != 0:
            raise VersionError(
                f"version command exited {process.returncode} executable={command[0]} "
                "fix_hint=inspect-command-stderr"
            )
        return process


def _safe_repository_path(root: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise VersionError(f"{field} must be a non-empty repository-relative path")
    candidate = Path(value)
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if candidate.is_absolute() or not resolved.is_relative_to(resolved_root):
        raise VersionError(f"unsafe path field={field} value={value!r}")
    if not resolved.is_file():
        raise VersionError(f"missing version file field={field} value={value!r}")
    return resolved


def _unique_strings(value: Any, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise VersionError(f"{field} must be a unique non-empty string list")
    return tuple(value)


def _json_field_path(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise VersionError(f"{field} must be a non-empty string path")
    return tuple(value)


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _ensure_incrementing(
    current: StableVersion,
    *,
    base: StableVersion | None,
    released: Iterable[StableVersion],
) -> None:
    if base is not None and current <= base:
        raise VersionError(
            f"version {current} must be greater than base {base}; fix_hint=run-make-version-bump"
        )
    released_versions = tuple(released)
    if current in released_versions:
        raise VersionError(f"version tag {current.tag} already exists; fix_hint=bump-version")
    if released_versions and current <= max(released_versions):
        raise VersionError(
            f"version {current} must be greater than released {max(released_versions)}; "
            "fix_hint=bump-version"
        )


def _ensure_releasable(
    current: StableVersion,
    *,
    base: StableVersion | None,
    tagged: Iterable[StableVersion],
    released: Iterable[StableVersion],
    existing_at_sha: str | None,
    tag_commit: str | None,
) -> None:
    tagged_versions = tuple(tagged)
    released_versions = tuple(released)
    current_exists = current in tagged_versions or current in released_versions
    if current_exists:
        if existing_at_sha is None or tag_commit != existing_at_sha.lower():
            raise VersionError(
                f"version tag {current.tag} already exists on another or unknown revision; "
                "fix_hint=bump-version-or-resume-the-original-sha"
            )
        tagged_versions = tuple(value for value in tagged_versions if value != current)
        released_versions = tuple(value for value in released_versions if value != current)
    # A failed publication leaves the source version on main without creating a tag or release.
    # Permit a repair PR to publish that still-unreleased version. Once a tag or release exists,
    # the existing-at-SHA rule above remains the only retry path.
    if not current_exists and base == current:
        return
    _ensure_incrementing(
        current,
        base=base,
        released=(*tagged_versions, *released_versions),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subcommands = parser.add_subparsers(dest="command", required=True)
    show = subcommands.add_parser("show")
    show.add_argument("--channel", choices=("stable", "snapshot"), default="stable")
    show.add_argument("--run-number", type=int)
    show.add_argument("--sha")
    show.add_argument("--json", action="store_true")
    check = subcommands.add_parser("check")
    check.add_argument("--base-ref")
    check.add_argument("--require-unreleased", action="store_true")
    check.add_argument("--github-repository")
    check.add_argument("--allow-existing-at-sha")
    set_version = subcommands.add_parser("set")
    set_version.add_argument("version")
    set_version.add_argument("--dry-run", action="store_true")
    set_version.add_argument("--allow-dirty", action="store_true")
    bump = subcommands.add_parser("bump")
    bump.add_argument("--part", required=True, choices=("major", "minor", "patch"))
    bump.add_argument("--dry-run", action="store_true")
    bump.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = parse_args()
    try:
        configuration = VersionConfiguration.load(args.config)
        synchronizer = VersionSynchronizer(configuration)
        history = GitVersionHistory(
            configuration.root,
            timeout_seconds=configuration.command_timeout_seconds,
        )
        if args.command == "show":
            stable = synchronizer.check()
            if args.channel == "snapshot":
                if args.run_number is None or args.sha is None:
                    raise VersionError("snapshot show requires --run-number and --sha")
                resolved = stable.snapshot(run_number=args.run_number, commit_sha=args.sha)
            else:
                resolved = stable.release()
            print(json.dumps(resolved.as_dict(), sort_keys=True) if args.json else resolved.oci_tag)
        elif args.command == "check":
            stable = synchronizer.check()
            base = (
                history.version_at(args.base_ref, configuration.authority)
                if args.base_ref
                else None
            )
            released: list[StableVersion] = []
            if args.require_unreleased:
                tagged = history.stable_tags()
                if args.github_repository:
                    released.extend(history.github_release_tags(args.github_repository))
                if (
                    args.allow_existing_at_sha
                    and _COMMIT_SHA.fullmatch(args.allow_existing_at_sha) is None
                ):
                    raise VersionError("--allow-existing-at-sha must be a hexadecimal Git SHA")
                _ensure_releasable(
                    stable,
                    base=base,
                    tagged=tagged,
                    released=released,
                    existing_at_sha=args.allow_existing_at_sha,
                    tag_commit=history.tag_commit(stable.tag),
                )
            elif base is not None:
                _ensure_incrementing(stable, base=base, released=())
            print(stable)
        else:
            if not args.allow_dirty:
                history.ensure_clean()
            current = synchronizer.authority()
            target = (
                StableVersion.parse(args.version)
                if args.command == "set"
                else current.bump(args.part)
            )
            diff = synchronizer.update(target, dry_run=args.dry_run)
            if diff:
                print(diff, end="")
            print(target)
    except VersionError as error:
        LOGGER.error("event=version.failed error=%s", error)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
