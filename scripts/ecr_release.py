"""Verify, scan, and safely retag immutable multi-platform ECR releases.

Protocol references:
https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_BatchGetImage.html
https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_DescribeImageScanFindings.html
https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_PutImage.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INDEX_MEDIA_TYPES = (
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
)
IMAGE_MEDIA_TYPES = (
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
)
WAITING_SCAN_STATES = frozenset({"ACTIVE", "IN_PROGRESS", "PENDING"})


class ReleaseError(RuntimeError):
    """Actionable ECR release contract failure."""


@dataclass(frozen=True)
class ManifestImage:
    digest: str
    platform: str


def emit(event: str, **fields: Any) -> None:
    """Emit stable JSON events without credentials or manifest bodies."""
    print(json.dumps({"event": event, **fields}, sort_keys=True), file=sys.stderr, flush=True)


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ReleaseError(f"unsupported release config schema: {config.get('schema_version')}")
    return config


def normalized_platform(platform: dict[str, str]) -> str | None:
    os_name = platform.get("os")
    architecture = platform.get("architecture")
    if not os_name or not architecture or architecture == "unknown" or os_name == "unknown":
        return None
    return f"{os_name}/{architecture}"


def get_manifest_index(ecr: Any, repository: str, image_id: dict[str, str]) -> dict[str, Any]:
    emit("ecr.manifest.get.before", repository=repository, image_id=image_id)
    response = ecr.batch_get_image(
        repositoryName=repository,
        imageIds=[image_id],
        acceptedMediaTypes=list(INDEX_MEDIA_TYPES),
    )
    failures = response.get("failures", [])
    if failures or not response.get("images"):
        emit("ecr.manifest.get.failed", repository=repository, failures=failures)
        reason = failures or "not found"
        raise ReleaseError(f"ECR manifest lookup failed for {repository}: {reason}")
    image = response["images"][0]
    media_type = image.get("imageManifestMediaType")
    manifest = json.loads(image["imageManifest"])
    effective_type = media_type or manifest.get("mediaType")
    if effective_type not in INDEX_MEDIA_TYPES:
        raise ReleaseError(
            f"{repository} is not a multi-platform index: media_type={effective_type!r}"
        )
    emit(
        "ecr.manifest.get.after",
        repository=repository,
        media_type=effective_type,
        entries=len(manifest.get("manifests", [])),
    )
    return {"manifest": manifest, "media_type": effective_type, "image": image}


def verify_platforms(
    manifest: dict[str, Any], expected_platforms: Sequence[str]
) -> list[ManifestImage]:
    found: dict[str, str] = {}
    for entry in manifest.get("manifests", []):
        platform = normalized_platform(entry.get("platform", {}))
        if platform:
            found[platform] = entry["digest"]
    missing = sorted(set(expected_platforms) - found.keys())
    if missing:
        emit("ecr.platform.verify.failed", expected=list(expected_platforms), found=sorted(found))
        raise ReleaseError(f"multi-platform index is missing: {', '.join(missing)}")
    images = [
        ManifestImage(digest=found[platform], platform=platform) for platform in expected_platforms
    ]
    emit("ecr.platform.verify.after", platforms=[image.platform for image in images])
    return images


def _error_code(error: Exception) -> str | None:
    response = getattr(error, "response", {})
    return response.get("Error", {}).get("Code") if isinstance(response, dict) else None


def wait_for_scan(
    ecr: Any,
    repository: str,
    image: ManifestImage,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = monotonic() + timeout_seconds
    scan_requested = False
    emit(
        "ecr.scan.wait.before",
        repository=repository,
        digest=image.digest,
        platform=image.platform,
        timeout_seconds=timeout_seconds,
    )
    while monotonic() <= deadline:
        try:
            response = ecr.describe_image_scan_findings(
                repositoryName=repository,
                imageId={"imageDigest": image.digest},
                maxResults=1000,
            )
        except Exception as error:
            code = _error_code(error)
            if code == "ScanNotFoundException" and not scan_requested:
                emit("ecr.scan.start.before", repository=repository, digest=image.digest)
                ecr.start_image_scan(
                    repositoryName=repository,
                    imageId={"imageDigest": image.digest},
                )
                scan_requested = True
                emit("ecr.scan.start.after", repository=repository, digest=image.digest)
                sleeper(poll_interval_seconds)
                continue
            raise
        status = response.get("imageScanStatus", {}).get("status", "UNKNOWN")
        emit(
            "ecr.scan.poll",
            repository=repository,
            digest=image.digest,
            platform=image.platform,
            status=status,
        )
        if status == "COMPLETE":
            counts = response.get("imageScanFindings", {}).get("findingSeverityCounts", {})
            emit(
                "ecr.scan.wait.after",
                repository=repository,
                digest=image.digest,
                platform=image.platform,
                severity_counts=counts,
            )
            return {"digest": image.digest, "platform": image.platform, "severity_counts": counts}
        if status not in WAITING_SCAN_STATES:
            description = response.get("imageScanStatus", {}).get("description", "")
            raise ReleaseError(
                f"ECR scan failed for {repository}@{image.digest}: {status} {description}".strip()
            )
        sleeper(poll_interval_seconds)
    raise ReleaseError(
        f"ECR scan timed out after {timeout_seconds}s for {repository}@{image.digest}; "
        "increase scan.timeout_seconds or inspect ECR/Inspector events"
    )


def enforce_scan_policy(results: Sequence[dict[str, Any]], fail_severities: Sequence[str]) -> None:
    violations: list[str] = []
    for result in results:
        counts = result["severity_counts"]
        for severity in fail_severities:
            count = int(counts.get(severity, 0))
            if count:
                violations.append(f"{result['platform']}:{severity}={count}")
    if violations:
        emit("ecr.scan.policy.failed", violations=violations)
        raise ReleaseError("ECR vulnerability policy rejected release: " + ", ".join(violations))
    emit("ecr.scan.policy.after", fail_severities=list(fail_severities))


def verify_and_scan(
    ecr: Any,
    *,
    repository: str,
    tag: str,
    expected_digest: str | None,
    platforms: Sequence[str],
    timeout_seconds: float,
    poll_interval_seconds: float,
    fail_severities: Sequence[str],
) -> dict[str, Any]:
    index = get_manifest_index(ecr, repository, {"imageTag": tag})
    actual_digest = index["image"].get("imageId", {}).get("imageDigest")
    if expected_digest and actual_digest != expected_digest:
        raise ReleaseError(
            f"digest mismatch for {repository}:{tag}: "
            f"expected={expected_digest} actual={actual_digest}"
        )
    images = verify_platforms(index["manifest"], platforms)
    scan_results = [
        wait_for_scan(
            ecr,
            repository,
            image,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        for image in images
    ]
    enforce_scan_policy(scan_results, fail_severities)
    return {
        "action": "verify-and-scan",
        "repository": repository,
        "tag": tag,
        "digest": actual_digest,
        "media_type": index["media_type"],
        "platforms": scan_results,
        "policy": {"fail_severities": list(fail_severities), "passed": True},
    }


def rollback(ecr: Any, *, repository: str, source_digest: str, target_tag: str) -> dict[str, Any]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", source_digest):
        raise ReleaseError("rollback source digest must be a complete lowercase sha256 digest")
    if not target_tag or target_tag == "latest":
        raise ReleaseError("rollback requires a new immutable target tag; latest is forbidden")
    index = get_manifest_index(ecr, repository, {"imageDigest": source_digest})
    emit(
        "ecr.rollback.put.before",
        repository=repository,
        source_digest=source_digest,
        target_tag=target_tag,
    )
    response = ecr.put_image(
        repositoryName=repository,
        imageManifest=index["image"]["imageManifest"],
        imageManifestMediaType=index["media_type"],
        imageTag=target_tag,
    )
    resulting_digest = response.get("image", {}).get("imageId", {}).get("imageDigest")
    if resulting_digest and resulting_digest != source_digest:
        raise ReleaseError(
            f"rollback digest changed: source={source_digest} resulting={resulting_digest}"
        )
    emit(
        "ecr.rollback.put.after",
        repository=repository,
        digest=source_digest,
        target_tag=target_tag,
    )
    return {
        "action": "rollback",
        "repository": repository,
        "source_digest": source_digest,
        "target_tag": target_tag,
        "digest": resulting_digest or source_digest,
    }


def component_config(config: dict[str, Any], name: str) -> dict[str, str]:
    for component in config["components"]:
        if component["name"] == name:
            return component
    raise ReleaseError(f"unknown component {name!r}; update config/ecr-release.json")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=Path("config/ecr-release.json"))
    result.add_argument("--region")
    result.add_argument("--report", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-and-scan")
    verify.add_argument("--component", required=True)
    verify.add_argument("--tag", required=True)
    verify.add_argument("--expected-digest")
    rollback_command = commands.add_parser("rollback")
    rollback_command.add_argument("--component", required=True)
    rollback_command.add_argument("--source-digest", required=True)
    rollback_command.add_argument("--target-tag", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        component = component_config(config, args.component)
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*", component["repository"]):
            raise ReleaseError(f"invalid ECR repository name: {component['repository']!r}")
        import boto3

        ecr = boto3.client("ecr", region_name=args.region)
        if args.command == "verify-and-scan":
            scan = config["scan"]
            result = verify_and_scan(
                ecr,
                repository=component["repository"],
                tag=args.tag,
                expected_digest=args.expected_digest,
                platforms=config["platforms"],
                timeout_seconds=scan["timeout_seconds"],
                poll_interval_seconds=scan["poll_interval_seconds"],
                fail_severities=scan["fail_severities"],
            )
        else:
            result = rollback(
                ecr,
                repository=component["repository"],
                source_digest=args.source_digest,
                target_tag=args.target_tag,
            )
        serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
        return 0
    except ReleaseError as error:
        emit(
            "ecr.release.failed",
            error_type=type(error).__name__,
            message=str(error),
            fix_hint="check docs/ecr-release.md and config/ecr-release.json",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
