"""OCI/Trivy release evidence derived from official specifications.

https://github.com/opencontainers/image-spec/blob/main/image-index.md
https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.registry_release import (
    ReleaseContractError,
    check_config,
    evaluate_scans,
    load_config,
    summarize_trivy,
    verify_index,
)

ROOT = Path(__file__).parents[1]


def image_index(*platforms: str) -> dict[str, object]:
    manifests = []
    for index, platform in enumerate(platforms):
        os_name, architecture = platform.split("/")
        manifests.append(
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": f"sha256:{index:064x}",
                "platform": {"os": os_name, "architecture": architecture},
            }
        )
    manifests.append(
        {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": "sha256:" + "f" * 64,
            "platform": {"os": "unknown", "architecture": "unknown"},
        }
    )
    return {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": manifests,
    }


def test_verify_index_requires_every_runtime_platform_and_ignores_attestations() -> None:
    result = verify_index(image_index("linux/amd64", "linux/arm64"), ["linux/amd64", "linux/arm64"])

    assert [item["platform"] for item in result] == ["linux/amd64", "linux/arm64"]


def test_verify_index_reports_missing_platform() -> None:
    with pytest.raises(ReleaseContractError, match="linux/arm64"):
        verify_index(image_index("linux/amd64"), ["linux/amd64", "linux/arm64"])


def test_verify_index_rejects_a_single_platform_manifest() -> None:
    with pytest.raises(ReleaseContractError, match="mediaType"):
        verify_index(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "manifests": [],
            },
            ["linux/amd64"],
        )


def test_trivy_summary_handles_missing_and_multiple_result_sections() -> None:
    report = {
        "Results": [
            {"Vulnerabilities": [{"Severity": "HIGH"}, {"Severity": "CRITICAL"}]},
            {"Vulnerabilities": None},
            {"Vulnerabilities": [{"Severity": "high"}]},
        ]
    }

    assert summarize_trivy(report) == {"HIGH": 2, "CRITICAL": 1}


def test_scan_policy_evaluates_all_platforms_before_rejecting() -> None:
    with pytest.raises(ReleaseContractError, match="linux/arm64:CRITICAL=1"):
        evaluate_scans(
            [
                ("linux/amd64", {"Results": []}),
                (
                    "linux/arm64",
                    {"Results": [{"Vulnerabilities": [{"Severity": "CRITICAL"}]}]},
                ),
            ],
            ["CRITICAL"],
        )


def test_scan_policy_returns_auditable_counts() -> None:
    result = evaluate_scans(
        [
            (
                "linux/amd64",
                {"Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}]},
            ),
            ("linux/arm64", {"Results": []}),
        ],
        ["CRITICAL"],
    )

    assert result["passed"] is True
    assert result["platforms"][0]["severity_counts"] == {"LOW": 1}


def test_committed_release_config_references_real_builds_and_official_sources() -> None:
    config = load_config(ROOT / "config/registry-release.json")

    report = check_config(config, ROOT)

    assert report["registry"] == "ghcr.io"
    assert report["components"] == ["proxy", "emr", "glue"]
    assert all((ROOT / item["dockerfile"]).is_file() for item in config["components"])
    serialized = json.dumps(config)
    assert "docs.github.com" in serialized
    assert "opencontainers/image-spec" in serialized
