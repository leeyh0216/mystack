"""Shared, ignored locations for deterministic compatibility build artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "compatibility"


def artifact(name: str) -> Path:
    """Return a named compatibility artifact under the ignored CI/local output root."""

    return ARTIFACT_ROOT / name


EVIDENCE_JSON = artifact("compatibility-evidence.json")
MATRIX_JSON = artifact("compatibility-matrix.json")
API_COVERAGE_JSON = artifact("api-coverage.json")
ANNOTATED_EVIDENCE_ENGLISH = artifact("annotated-evidence.md")
ANNOTATED_EVIDENCE_KOREAN = artifact("annotated-evidence.ko.md")
CLIENT_MATRIX_ENGLISH = artifact("client-matrix.md")
CLIENT_MATRIX_KOREAN = artifact("client-matrix.ko.md")
RELEASE_ACCEPTANCE_ENGLISH = artifact("release-acceptance.md")
RELEASE_ACCEPTANCE_KOREAN = artifact("release-acceptance.ko.md")
GLUE_ERRORS_ENGLISH = artifact("glue-errors.md")
GLUE_ERRORS_KOREAN = artifact("glue-errors.ko.md")
