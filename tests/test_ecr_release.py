"""ECR release contracts derived from the official API reference.

https://docs.aws.amazon.com/AmazonECR/latest/APIReference/Welcome.html
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.ecr_release import (
    ManifestImage,
    ReleaseError,
    enforce_scan_policy,
    rollback,
    verify_platforms,
    wait_for_scan,
)

ROOT = Path(__file__).parents[1]


class FakeEcr:
    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = responses or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def describe_image_scan_findings(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("describe_image_scan_findings", kwargs))
        return self.responses.pop(0)

    def batch_get_image(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("batch_get_image", kwargs))
        manifest = {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "digest": "sha256:amd64",
                    "platform": {"os": "linux", "architecture": "amd64"},
                },
                {
                    "digest": "sha256:arm64",
                    "platform": {"os": "linux", "architecture": "arm64", "variant": "v8"},
                },
            ],
        }
        return {
            "images": [
                {
                    "imageId": {"imageDigest": kwargs["imageIds"][0].get("imageDigest")},
                    "imageManifest": json.dumps(manifest),
                    "imageManifestMediaType": "application/vnd.oci.image.index.v1+json",
                }
            ],
            "failures": [],
        }

    def put_image(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("put_image", kwargs))
        return {"image": {"imageId": {"imageDigest": "sha256:" + "a" * 64}}}


def test_verify_platforms_ignores_attestations_and_requires_both_architectures() -> None:
    manifest = {
        "manifests": [
            {"digest": "sha256:a", "platform": {"os": "linux", "architecture": "amd64"}},
            {"digest": "sha256:b", "platform": {"os": "linux", "architecture": "arm64"}},
            {"digest": "sha256:c", "platform": {"os": "unknown", "architecture": "unknown"}},
        ]
    }

    images = verify_platforms(manifest, ["linux/amd64", "linux/arm64"])

    assert images == [
        ManifestImage("sha256:a", "linux/amd64"),
        ManifestImage("sha256:b", "linux/arm64"),
    ]


def test_verify_platforms_reports_missing_platform() -> None:
    with pytest.raises(ReleaseError, match="linux/arm64"):
        verify_platforms(
            {
                "manifests": [
                    {
                        "digest": "sha256:a",
                        "platform": {"os": "linux", "architecture": "amd64"},
                    }
                ]
            },
            ["linux/amd64", "linux/arm64"],
        )


def test_wait_for_scan_polls_to_completion_without_real_sleep() -> None:
    ecr = FakeEcr(
        [
            {"imageScanStatus": {"status": "IN_PROGRESS"}},
            {
                "imageScanStatus": {"status": "COMPLETE"},
                "imageScanFindings": {"findingSeverityCounts": {"LOW": 2}},
            },
        ]
    )
    clock = iter([0.0, 0.0, 1.0])

    result = wait_for_scan(
        ecr,
        "mystack-proxy",
        ManifestImage("sha256:a", "linux/amd64"),
        timeout_seconds=10,
        poll_interval_seconds=1,
        monotonic=lambda: next(clock),
        sleeper=lambda _: None,
    )

    assert result["severity_counts"] == {"LOW": 2}
    assert [call[0] for call in ecr.calls] == [
        "describe_image_scan_findings",
        "describe_image_scan_findings",
    ]


def test_scan_policy_rejects_configured_severity() -> None:
    with pytest.raises(ReleaseError, match="linux/arm64:CRITICAL=1"):
        enforce_scan_policy(
            [{"platform": "linux/arm64", "severity_counts": {"CRITICAL": 1}}],
            ["CRITICAL"],
        )


def test_rollback_adds_new_tag_to_exact_existing_index() -> None:
    ecr = FakeEcr()

    result = rollback(
        ecr,
        repository="mystack-emr",
        source_digest="sha256:" + "a" * 64,
        target_tag="rollback-42-1",
    )

    assert result["digest"] == "sha256:" + "a" * 64
    put = next(arguments for name, arguments in ecr.calls if name == "put_image")
    assert put["imageTag"] == "rollback-42-1"
    assert put["imageManifestMediaType"] == "application/vnd.oci.image.index.v1+json"


def test_rollback_forbids_mutable_latest_tag() -> None:
    with pytest.raises(ReleaseError, match="latest is forbidden"):
        rollback(
            FakeEcr(),
            repository="mystack-glue",
            source_digest="sha256:" + "a" * 64,
            target_tag="latest",
        )


def test_release_config_references_existing_component_builds_and_official_sources() -> None:
    config = json.loads((ROOT / "config/ecr-release.json").read_text(encoding="utf-8"))

    assert config["schema_version"] == 1
    assert len(config["platforms"]) == len(set(config["platforms"]))
    assert len(config["components"]) == len(
        {component["name"] for component in config["components"]}
    )
    for component in config["components"]:
        assert (ROOT / component["dockerfile"]).is_file()
    official_prefixes = (
        "https://docs.aws.amazon.com",
        "https://docs.github.com",
        "https://github.com/docker/",
    )
    assert all(source.startswith(official_prefixes) for source in config["official_sources"])
