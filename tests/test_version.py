"""Version authority and non-publishing tooling contracts.

Official references:
- https://semver.org/
- https://packaging.python.org/en/latest/specifications/version-specifiers/
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.version import (
    DEFAULT_CONFIG,
    ROOT,
    StableVersion,
    VersionConfiguration,
    VersionError,
    VersionSynchronizer,
    _ensure_incrementing,
    _ensure_releasable,
)


def test_repository_version_authority_and_every_derived_file_are_in_sync() -> None:
    configuration = VersionConfiguration.load(DEFAULT_CONFIG)
    synchronizer = VersionSynchronizer(configuration)
    expected = StableVersion.parse((ROOT / "VERSION").read_text(encoding="utf-8"))

    assert synchronizer.check() == expected
    assert synchronizer.drift() == {}


@pytest.mark.parametrize(
    "value",
    ["1.2", "v1.2.3", "1.2.3-snapshot", "1.2.3+build", "01.2.3", "1.02.3", "1.2.03"],
)
def test_stable_version_rejects_non_core_or_ambiguous_values(value: str) -> None:
    with pytest.raises(VersionError, match="invalid stable version"):
        StableVersion.parse(value)


def test_bump_and_snapshot_rendering_keep_semver_oci_and_pep440_distinct() -> None:
    version = StableVersion.parse("1.2.3")

    assert version.bump("major") == StableVersion(2, 0, 0)
    assert version.bump("minor") == StableVersion(1, 3, 0)
    assert version.bump("patch") == StableVersion(1, 2, 4)
    assert version.release().as_dict() == {
        "stable_version": "1.2.3",
        "channel": "stable",
        "oci_tag": "v1.2.3",
        "python_version": "1.2.3",
    }
    assert version.snapshot(run_number=842, commit_sha="1A2B3C4d999").as_dict() == {
        "stable_version": "1.2.3",
        "channel": "snapshot",
        "oci_tag": "v1.2.3-snapshot.842.g1a2b3c4d",
        "python_version": "1.2.3.dev842+g1a2b3c4d",
    }


def test_non_incrementing_duplicate_and_older_versions_are_rejected() -> None:
    with pytest.raises(VersionError, match="greater than base"):
        _ensure_incrementing(
            StableVersion.parse("1.2.3"),
            base=StableVersion.parse("1.2.3"),
            released=(),
        )


def test_release_retry_allows_only_the_same_version_on_the_same_sha() -> None:
    current = StableVersion.parse("1.2.3")
    sha = "1234567890abcdef1234567890abcdef12345678"

    _ensure_releasable(
        current,
        base=StableVersion.parse("1.2.2"),
        tagged=(current,),
        released=(current,),
        existing_at_sha=sha,
        tag_commit=sha,
    )
    with pytest.raises(VersionError, match="another or unknown revision"):
        _ensure_releasable(
            current,
            base=StableVersion.parse("1.2.2"),
            tagged=(current,),
            released=(),
            existing_at_sha=sha,
            tag_commit="abcdef1234567890abcdef1234567890abcdef12",
        )
    with pytest.raises(VersionError, match="already exists"):
        _ensure_incrementing(
            StableVersion.parse("1.2.3"),
            base=None,
            released=(StableVersion.parse("1.2.3"),),
        )
    with pytest.raises(VersionError, match="greater than released"):
        _ensure_incrementing(
            StableVersion.parse("1.2.3"),
            base=None,
            released=(StableVersion.parse("2.0.0"),),
        )


def test_dry_run_renders_all_configured_file_kinds_without_writing(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "package.json").write_text(
        json.dumps({"version": "1.2.3"}, indent=2) + "\n", encoding="utf-8"
    )
    (tmp_path / "Dockerfile").write_text("ARG VERSION=1.2.3\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "demo"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    config_path = tmp_path / "version.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "authority": "VERSION",
                "command_timeout_seconds": 1,
                "files": [
                    {"path": "pyproject.toml", "kind": "toml-project"},
                    {"path": "package.json", "kind": "json", "fields": [["version"]]},
                    {"path": "uv.lock", "kind": "uv-lock", "packages": ["demo"]},
                    {
                        "path": "Dockerfile",
                        "kind": "regex",
                        "pattern": "ARG VERSION=[0-9]+\\.[0-9]+\\.[0-9]+",
                        "replacement": "ARG VERSION={version}",
                        "expected_matches": 1,
                    },
                ],
                "official_sources": ["https://semver.org/"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    configuration = VersionConfiguration.load(config_path, root=tmp_path)
    synchronizer = VersionSynchronizer(configuration)

    diff = synchronizer.update(StableVersion.parse("1.3.0"), dry_run=True)

    assert '-version = "1.2.3"' in diff
    assert '+version = "1.3.0"' in diff
    assert "-ARG VERSION=1.2.3" in diff
    assert "+ARG VERSION=1.3.0" in diff
    assert (tmp_path / "VERSION").read_text(encoding="utf-8") == "1.2.3\n"


def test_config_rejects_repository_escape_and_missing_markers(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    config = {
        "schema_version": 1,
        "authority": "VERSION",
        "command_timeout_seconds": 1,
        "files": [
            {
                "path": "../outside.txt",
                "kind": "regex",
                "pattern": "version",
                "replacement": "{version}",
                "expected_matches": 1,
            }
        ],
        "official_sources": ["https://semver.org/"],
    }
    config_path = tmp_path / "version.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(VersionError, match="unsafe path"):
        VersionConfiguration.load(config_path, root=tmp_path)


def test_default_version_config_is_repository_relative() -> None:
    assert DEFAULT_CONFIG == ROOT / "config/release/version-files.json"
