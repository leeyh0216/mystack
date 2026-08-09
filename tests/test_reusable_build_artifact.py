from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from scripts.reusable_build_artifact import ArtifactError, create, verify


def _arguments(root: Path, manifest: Path) -> argparse.Namespace:
    return argparse.Namespace(
        root=root,
        manifest=manifest,
        source_sha="a" * 40,
        platform="Linux-X64",
        input=[Path("package-lock.json"), Path(".node-version")],
        artifact=[Path("ui")],
        producer_workflow="CI",
        producer_run_id="42",
        retention_days=2,
    )


def test_matching_manifest_verifies(tmp_path: Path) -> None:
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "app.js").write_text("bundle", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("lock", encoding="utf-8")
    (tmp_path / ".node-version").write_text("22", encoding="utf-8")
    arguments = _arguments(tmp_path, tmp_path / "manifest.json")
    arguments.manifest.write_text(__import__("json").dumps(create(arguments)), encoding="utf-8")

    verify(arguments)


@pytest.mark.parametrize("field", ["source_sha", "platform"])
def test_stale_identity_is_rejected(tmp_path: Path, field: str) -> None:
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "app.js").write_text("bundle", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("lock", encoding="utf-8")
    (tmp_path / ".node-version").write_text("22", encoding="utf-8")
    arguments = _arguments(tmp_path, tmp_path / "manifest.json")
    manifest = create(arguments)
    arguments.manifest.write_text(__import__("json").dumps(manifest), encoding="utf-8")
    setattr(arguments, field, "different" if field == "platform" else "b" * 40)

    with pytest.raises(ArtifactError, match="mismatch"):
        verify(arguments)


def test_corrupt_bundle_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "ui").mkdir()
    bundle = tmp_path / "ui" / "app.js"
    bundle.write_text("bundle", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("lock", encoding="utf-8")
    (tmp_path / ".node-version").write_text("22", encoding="utf-8")
    arguments = _arguments(tmp_path, tmp_path / "manifest.json")
    arguments.manifest.write_text(__import__("json").dumps(create(arguments)), encoding="utf-8")
    bundle.write_text("corrupt", encoding="utf-8")

    with pytest.raises(ArtifactError, match="file digest mismatch"):
        verify(arguments)
