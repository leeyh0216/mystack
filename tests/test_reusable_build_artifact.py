from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from scripts.reusable_build_artifact import ArtifactError, create, should_rebuild, verify

ROOT = Path(__file__).parents[1]


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


def test_only_unavailable_download_selects_fallback_rebuild() -> None:
    assert should_rebuild("success") is False
    assert should_rebuild("failure") is True
    assert should_rebuild("skipped") is True


def test_workflows_use_exact_cache_and_verified_cross_run_artifacts() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    e2e = (ROOT / ".github/workflows/e2e.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    publish = (ROOT / ".github/workflows/container-publish.yml").read_text(encoding="utf-8")

    assert "actions/cache/restore" in ci
    assert "actions/cache/save" in ci
    assert "restore-keys:" not in ci
    assert "service-ui-builds-${{ github.sha }}" in ci
    assert "workflow_run:" in e2e
    assert "run-id: ${{ github.event.workflow_run.id }}" in e2e
    assert "reusable_build_artifact.py verify" in e2e
    assert "ci_run_id: ${{ github.event.workflow_run.id }}" in release
    assert "run-id: ${{ inputs.ci_run_id }}" in publish
    assert "reusable_build_artifact.py verify" in publish
