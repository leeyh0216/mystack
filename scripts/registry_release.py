"""Validate a published OCI image index and Trivy reports without emulating either protocol.

Official contracts:
https://github.com/opencontainers/image-spec/blob/main/image-index.md
https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

INDEX_MEDIA_TYPES = frozenset(
    {
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.index.v1+json",
    }
)


class ReleaseContractError(RuntimeError):
    """Actionable release evidence failure."""


def emit(event: str, **fields: Any) -> None:
    """Write stable structured events without registry credentials or image layers."""
    print(json.dumps({"event": event, **fields}, sort_keys=True), file=sys.stderr, flush=True)


def load_config(path: Path) -> dict[str, Any]:
    emit("registry.config.read.before", path=str(path))
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ReleaseContractError(
            f"unsupported registry release schema: {config.get('schema_version')}"
        )
    components = config.get("components", [])
    if not components or len({item["name"] for item in components}) != len(components):
        raise ReleaseContractError("release components must be non-empty and uniquely named")
    if len(config.get("platforms", [])) != len(set(config.get("platforms", []))):
        raise ReleaseContractError("release platforms must be unique")
    emit(
        "registry.config.read.after",
        registry=config.get("registry"),
        components=len(components),
        platforms=config.get("platforms", []),
    )
    return config


def component_config(config: dict[str, Any], name: str) -> dict[str, str]:
    for component in config["components"]:
        if component["name"] == name:
            return component
    raise ReleaseContractError(
        f"unknown component {name!r}; update config/registry-release.json and generated matrix"
    )


def normalized_platform(descriptor: dict[str, Any]) -> str | None:
    platform = descriptor.get("platform", {})
    os_name = platform.get("os")
    architecture = platform.get("architecture")
    if not os_name or not architecture or "unknown" in {os_name, architecture}:
        return None
    return f"{os_name}/{architecture}"


def verify_index(
    manifest: dict[str, Any], expected_platforms: Sequence[str]
) -> list[dict[str, str]]:
    emit("registry.index.verify.before", expected_platforms=list(expected_platforms))
    if manifest.get("schemaVersion") != 2:
        raise ReleaseContractError(
            f"OCI image index schemaVersion must be 2, got {manifest.get('schemaVersion')!r}"
        )
    media_type = manifest.get("mediaType")
    if media_type not in INDEX_MEDIA_TYPES:
        raise ReleaseContractError(f"unsupported multi-platform index mediaType: {media_type!r}")
    found: dict[str, str] = {}
    for descriptor in manifest.get("manifests", []):
        platform = normalized_platform(descriptor)
        if platform:
            found[platform] = descriptor["digest"]
    missing = sorted(set(expected_platforms) - found.keys())
    if missing:
        emit("registry.index.verify.failed", missing=missing, found=sorted(found))
        raise ReleaseContractError(f"published OCI index is missing: {', '.join(missing)}")
    result = [{"platform": platform, "digest": found[platform]} for platform in expected_platforms]
    emit("registry.index.verify.after", platforms=result)
    return result


def summarize_trivy(report: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for result in report.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = vulnerability.get("Severity", "UNKNOWN").upper()
            counts[severity] += 1
    return counts


def evaluate_scans(
    scans: Sequence[tuple[str, dict[str, Any]]], fail_severities: Sequence[str]
) -> dict[str, Any]:
    emit(
        "registry.scan.evaluate.before",
        platforms=[platform for platform, _ in scans],
        fail_severities=list(fail_severities),
    )
    results: list[dict[str, Any]] = []
    violations: list[str] = []
    for platform, report in scans:
        counts = summarize_trivy(report)
        normalized_counts = dict(sorted(counts.items()))
        results.append({"platform": platform, "severity_counts": normalized_counts})
        for severity in fail_severities:
            count = counts[severity]
            if count:
                violations.append(f"{platform}:{severity}={count}")
    if violations:
        emit("registry.scan.evaluate.failed", violations=violations)
        raise ReleaseContractError(
            "Trivy vulnerability policy rejected published image: " + ", ".join(violations)
        )
    emit("registry.scan.evaluate.after", results=results)
    return {"passed": True, "fail_severities": list(fail_severities), "platforms": results}


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    emit("registry.report.write.after", path=str(path))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=Path("config/registry-release.json"))
    commands = result.add_subparsers(dest="command", required=True)

    config_command = commands.add_parser("check-config")
    config_command.add_argument("--root", type=Path, default=Path.cwd())

    index = commands.add_parser("verify-index")
    index.add_argument("--component", required=True)
    index.add_argument("--image", required=True)
    index.add_argument("--tag", required=True)
    index.add_argument("--digest", required=True)
    index.add_argument("--manifest", type=Path, required=True)
    index.add_argument("--report", type=Path, required=True)

    scans = commands.add_parser("evaluate-scans")
    scans.add_argument(
        "--scan",
        action="append",
        required=True,
        metavar="PLATFORM=PATH",
        help="Repeat for each configured platform",
    )
    scans.add_argument("--report", type=Path, required=True)
    return result


def check_config(config: dict[str, Any], root: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?", config.get("registry", "")):
        errors.append(f"invalid OCI registry host: {config.get('registry')!r}")
    for component in config["components"]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", component["package"]):
            errors.append(f"invalid package name: {component['package']!r}")
        if not (root / component["dockerfile"]).is_file():
            errors.append(f"missing Dockerfile: {component['dockerfile']}")
    if not config.get("official_sources") or not all(
        source.startswith("https://") for source in config["official_sources"]
    ):
        errors.append("official_sources must contain HTTPS references")
    if errors:
        raise ReleaseContractError("; ".join(errors))
    return {
        "schema_version": config["schema_version"],
        "registry": config["registry"],
        "components": [component["name"] for component in config["components"]],
        "platforms": config["platforms"],
    }


def parse_scans(values: Sequence[str]) -> list[tuple[str, dict[str, Any]]]:
    parsed: list[tuple[str, dict[str, Any]]] = []
    for value in values:
        platform, separator, raw_path = value.partition("=")
        if not separator or not platform or not raw_path:
            raise ReleaseContractError(f"invalid --scan value {value!r}; expected PLATFORM=PATH")
        path = Path(raw_path)
        emit("registry.scan.read.before", platform=platform, path=str(path))
        parsed.append((platform, json.loads(path.read_text(encoding="utf-8"))))
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "check-config":
            report = check_config(config, args.root)
        elif args.command == "verify-index":
            component_config(config, args.component)
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.digest):
                raise ReleaseContractError("published digest must be a complete lowercase sha256")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            report = {
                "action": "publish",
                "registry": config["registry"],
                "component": args.component,
                "image": args.image,
                "tag": args.tag,
                "digest": args.digest,
                "media_type": manifest.get("mediaType"),
                "platforms": verify_index(manifest, config["platforms"]),
            }
            write_report(args.report, report)
        else:
            scans = parse_scans(args.scan)
            expected = config["platforms"]
            actual = [platform for platform, _ in scans]
            if actual != expected:
                raise ReleaseContractError(
                    "scan platforms must exactly follow config: "
                    f"expected={expected} actual={actual}"
                )
            report = evaluate_scans(scans, config["scan"]["fail_severities"])
            write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ReleaseContractError) as error:
        emit(
            "registry.release.failed",
            error_type=type(error).__name__,
            message=str(error),
            fix_hint="check docs/container-release.md and config/registry-release.json",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
