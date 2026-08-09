"""Validate a published OCI image index and Trivy reports without emulating either protocol.

Official contracts:
https://github.com/opencontainers/image-spec/blob/main/image-index.md
https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INDEX_MEDIA_TYPES = frozenset(
    {
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.index.v1+json",
    }
)
SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
SOURCE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
TAG_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,127}")
CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "registry",
        "consumer_visibility",
        "platforms",
        "components",
        "scan",
        "workflow_timeout_minutes",
        "preflight_timeout_minutes",
        "tags",
        "official_sources",
    }
)
COMPONENT_FIELDS = frozenset({"name", "package", "dockerfile"})
SCAN_FIELDS = frozenset({"trivy_version", "timeout", "ignore_unfixed", "fail_severities"})
TAG_FIELDS = frozenset(
    {"stable_pattern", "snapshot_pattern", "snapshot_retention_days", "publish_latest"}
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
    unknown = sorted(set(config) - CONFIG_FIELDS)
    missing = sorted(CONFIG_FIELDS - set(config))
    if unknown or missing:
        raise ReleaseContractError(
            f"registry config schema mismatch: unknown={unknown} missing={missing}"
        )
    components = config.get("components", [])
    if not components or len({item["name"] for item in components}) != len(components):
        raise ReleaseContractError("release components must be non-empty and uniquely named")
    if len(config.get("platforms", [])) != len(set(config.get("platforms", []))):
        raise ReleaseContractError("release platforms must be unique")
    for index, component in enumerate(components):
        _require_exact_fields(component, COMPONENT_FIELDS, f"components[{index}]")
    _require_exact_fields(config.get("scan"), SCAN_FIELDS, "scan")
    _require_exact_fields(config.get("tags"), TAG_FIELDS, "tags")
    emit(
        "registry.config.read.after",
        registry=config.get("registry"),
        consumer_visibility=config.get("consumer_visibility"),
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


def resolve_publication_plan(config: dict[str, Any]) -> dict[str, Any]:
    """Compile the configured component/platform product outside workflow shell syntax."""
    emit("registry.plan.compile.before", components=len(config["components"]))
    component_matrix = {"include": config["components"]}
    preflight_matrix = {
        "include": [
            {
                **component,
                "platform": platform,
                "platform_slug": platform_slug(platform),
            }
            for component in config["components"]
            for platform in config["platforms"]
        ]
    }
    expected = len(config["components"]) * len(config["platforms"])
    if len(preflight_matrix["include"]) != expected:
        raise ReleaseContractError("compiled preflight matrix cardinality mismatch")
    report = {
        "component_matrix": component_matrix,
        "preflight_matrix": preflight_matrix,
        "platforms": ",".join(config["platforms"]),
        "registry": config["registry"],
        "selection": "all",
        "trivy_version": config["scan"]["trivy_version"],
        "scan_timeout": config["scan"]["timeout"],
        "ignore_unfixed": config["scan"]["ignore_unfixed"],
        "workflow_timeout_minutes": config["workflow_timeout_minutes"],
        "preflight_timeout_minutes": config["preflight_timeout_minutes"],
        "snapshot_retention_days": config["tags"]["snapshot_retention_days"],
    }
    emit(
        "registry.plan.compile.after",
        components=len(component_matrix["include"]),
        preflights=len(preflight_matrix["include"]),
    )
    return report


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
    emit("registry.report.write.before", path=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    emit("registry.report.write.after", path=str(path))


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def platform_slug(platform: str) -> str:
    return platform.replace("/", "-")


@dataclass(frozen=True)
class PreflightEvidence:
    """One locally built and scanned component/platform pair."""

    component: str
    package: str
    dockerfile: str
    platform: str
    image_id: str
    source_sha: str
    version: str
    scan: dict[str, Any]

    def report(self) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "component": self.component,
            "package": self.package,
            "dockerfile": self.dockerfile,
            "platform": self.platform,
            "image_id": self.image_id,
            "source_sha": self.source_sha,
            "version": self.version,
            "scan": self.scan,
        }
        return {**body, "evidence_sha256": canonical_sha256(body)}


class ReleaseGate:
    """Verify complete preflight evidence without knowing GitHub Actions or a registry client."""

    RECORD_FIELDS = frozenset(
        {
            "schema_version",
            "component",
            "package",
            "dockerfile",
            "platform",
            "image_id",
            "source_sha",
            "version",
            "scan",
            "evidence_sha256",
        }
    )

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

    def selected_components(self, selection: str) -> list[dict[str, str]]:
        if selection == "all":
            return list(self._config["components"])
        return [component_config(self._config, selection)]

    def record(
        self,
        *,
        component: str,
        platform: str,
        image_id: str,
        source_sha: str,
        version: str,
        scan_report: dict[str, Any],
    ) -> dict[str, Any]:
        emit(
            "registry.preflight.record.before",
            component=component,
            platform=platform,
            source_sha=source_sha,
            version=version,
        )
        selected = component_config(self._config, component)
        self._validate_identity(platform, image_id, source_sha, version)
        scan = evaluate_scans([(platform, scan_report)], self._config["scan"]["fail_severities"])
        report = PreflightEvidence(
            component=component,
            package=selected["package"],
            dockerfile=selected["dockerfile"],
            platform=platform,
            image_id=image_id,
            source_sha=source_sha,
            version=version,
            scan=scan,
        ).report()
        emit(
            "registry.preflight.record.after",
            component=component,
            platform=platform,
            evidence_sha256=report["evidence_sha256"],
        )
        return report

    def verify(
        self,
        *,
        evidence_root: Path,
        selection: str,
        source_sha: str,
        version: str,
    ) -> dict[str, Any]:
        components = self.selected_components(selection)
        expected = [
            (component, platform)
            for component in components
            for platform in self._config["platforms"]
        ]
        emit(
            "registry.gate.verify.before",
            selection=selection,
            source_sha=source_sha,
            version=version,
            expected=len(expected),
        )
        records: list[dict[str, Any]] = []
        expected_paths: set[Path] = set()
        for component, platform in expected:
            path = (
                evidence_root
                / "preflight"
                / component["name"]
                / platform_slug(platform)
                / "preflight.json"
            )
            expected_paths.add(path.resolve())
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ReleaseContractError(
                    f"missing or invalid preflight evidence: {path}"
                ) from error
            self._validate_record(
                record,
                component=component,
                platform=platform,
                source_sha=source_sha,
                version=version,
            )
            records.append(record)
        actual_paths = {path.resolve() for path in evidence_root.rglob("preflight.json")}
        if actual_paths != expected_paths:
            unexpected = sorted(str(path) for path in actual_paths - expected_paths)
            missing = sorted(str(path) for path in expected_paths - actual_paths)
            raise ReleaseContractError(
                f"preflight evidence set mismatch: missing={missing} unexpected={unexpected}"
            )
        body = {
            "schema_version": 1,
            "authorized": True,
            "selection": selection,
            "components": [component["name"] for component in components],
            "platforms": self._config["platforms"],
            "source_sha": source_sha,
            "version": version,
            "records": sorted(records, key=lambda item: (item["component"], item["platform"])),
        }
        report = {**body, "authorization_sha256": canonical_sha256(body)}
        emit(
            "registry.gate.verify.after",
            authorization_sha256=report["authorization_sha256"],
            records=len(records),
        )
        return report

    def authorize(
        self,
        report: dict[str, Any],
        *,
        selection: str,
        source_sha: str,
        version: str,
    ) -> dict[str, Any]:
        emit(
            "registry.publication.authorize.before",
            selection=selection,
            source_sha=source_sha,
            version=version,
        )
        required = {
            "schema_version",
            "authorized",
            "selection",
            "components",
            "platforms",
            "source_sha",
            "version",
            "records",
            "authorization_sha256",
        }
        _require_exact_fields(report, frozenset(required), "gate-report")
        expected_components = [item["name"] for item in self.selected_components(selection)]
        if (
            report["schema_version"] != 1
            or report["authorized"] is not True
            or report["selection"] != selection
            or report["components"] != expected_components
            or report["platforms"] != self._config["platforms"]
            or report["source_sha"] != source_sha
            or report["version"] != version
        ):
            raise ReleaseContractError(
                "publication authorization context mismatch; fix_hint=rerun-complete-release"
            )
        body = {name: value for name, value in report.items() if name != "authorization_sha256"}
        if canonical_sha256(body) != report["authorization_sha256"]:
            raise ReleaseContractError("publication authorization digest mismatch")
        expected_records = len(expected_components) * len(self._config["platforms"])
        if len(report["records"]) != expected_records:
            raise ReleaseContractError("publication authorization record count mismatch")
        emit(
            "registry.publication.authorize.after",
            authorization_sha256=report["authorization_sha256"],
        )
        return {
            "authorized": True,
            "authorization_sha256": report["authorization_sha256"],
            "components": expected_components,
        }

    def _validate_record(
        self,
        record: dict[str, Any],
        *,
        component: dict[str, str],
        platform: str,
        source_sha: str,
        version: str,
    ) -> None:
        _require_exact_fields(record, self.RECORD_FIELDS, "preflight-record")
        if (
            record["schema_version"] != 1
            or record["component"] != component["name"]
            or record["package"] != component["package"]
            or record["dockerfile"] != component["dockerfile"]
            or record["platform"] != platform
            or record["source_sha"] != source_sha
            or record["version"] != version
            or record.get("scan", {}).get("passed") is not True
        ):
            raise ReleaseContractError(
                f"preflight evidence context mismatch: {component['name']} {platform}"
            )
        self._validate_identity(platform, record["image_id"], source_sha, version)
        body = {name: value for name, value in record.items() if name != "evidence_sha256"}
        if canonical_sha256(body) != record["evidence_sha256"]:
            raise ReleaseContractError(
                f"preflight evidence digest mismatch: {component['name']} {platform}"
            )

    def _validate_identity(
        self, platform: str, image_id: str, source_sha: str, version: str
    ) -> None:
        if platform not in self._config["platforms"]:
            raise ReleaseContractError(f"unknown preflight platform: {platform}")
        if not SHA256_PATTERN.fullmatch(image_id):
            raise ReleaseContractError("local image ID must be a complete lowercase sha256")
        if not SOURCE_SHA_PATTERN.fullmatch(source_sha):
            raise ReleaseContractError("source SHA must be a complete lowercase Git SHA-1")
        if not TAG_PATTERN.fullmatch(version):
            raise ReleaseContractError("version must be a valid OCI tag")


def _require_exact_fields(value: Any, expected: frozenset[str], path: str) -> None:
    if not isinstance(value, dict):
        raise ReleaseContractError(f"expected mapping at {path}")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown or missing:
        raise ReleaseContractError(
            f"schema mismatch at {path}: unknown={unknown} missing={missing}"
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=Path("config/registry-release.json"))
    commands = result.add_subparsers(dest="command", required=True)

    config_command = commands.add_parser("check-config")
    config_command.add_argument("--root", type=Path, default=Path.cwd())

    commands.add_parser("resolve-plan")

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

    preflight = commands.add_parser("record-preflight")
    preflight.add_argument("--component", required=True)
    preflight.add_argument("--platform", required=True)
    preflight.add_argument("--image-id", required=True)
    preflight.add_argument("--source-sha", required=True)
    preflight.add_argument("--version", required=True)
    preflight.add_argument("--scan", type=Path, required=True)
    preflight.add_argument("--report", type=Path, required=True)

    gate = commands.add_parser("verify-gate")
    gate.add_argument("--evidence-root", type=Path, required=True)
    gate.add_argument("--selection", required=True)
    gate.add_argument("--source-sha", required=True)
    gate.add_argument("--version", required=True)
    gate.add_argument("--report", type=Path, required=True)

    authorization = commands.add_parser("authorize-publication")
    authorization.add_argument("--gate", type=Path, required=True)
    authorization.add_argument("--selection", required=True)
    authorization.add_argument("--source-sha", required=True)
    authorization.add_argument("--version", required=True)
    return result


def check_config(config: dict[str, Any], root: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?", config.get("registry", "")):
        errors.append(f"invalid OCI registry host: {config.get('registry')!r}")
    if config.get("consumer_visibility") != "public":
        errors.append("consumer_visibility must be 'public' for anonymous image pulls")
    for component in config["components"]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", component["package"]):
            errors.append(f"invalid package name: {component['package']!r}")
        if not (root / component["dockerfile"]).is_file():
            errors.append(f"missing Dockerfile: {component['dockerfile']}")
    if not config["platforms"] or any(
        not re.fullmatch(r"linux/(amd64|arm64)", platform) for platform in config["platforms"]
    ):
        errors.append("platforms must be explicit supported Linux architecture strings")
    for timeout_name in ("workflow_timeout_minutes", "preflight_timeout_minutes"):
        timeout = config.get(timeout_name)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            errors.append(f"{timeout_name} must be a positive integer")
    for pattern_name in ("stable_pattern", "snapshot_pattern"):
        try:
            re.compile(config["tags"][pattern_name])
        except re.error:
            errors.append(f"tags.{pattern_name} must be a valid regular expression")
    retention = config["tags"].get("snapshot_retention_days")
    if not isinstance(retention, int) or isinstance(retention, bool) or retention <= 0:
        errors.append("tags.snapshot_retention_days must be a positive integer")
    if config["tags"].get("publish_latest") is not False:
        errors.append("tags.publish_latest must remain false until a moving-tag policy exists")
    if not config.get("official_sources") or not all(
        source.startswith("https://") for source in config["official_sources"]
    ):
        errors.append("official_sources must contain HTTPS references")
    if errors:
        raise ReleaseContractError("; ".join(errors))
    return {
        "schema_version": config["schema_version"],
        "registry": config["registry"],
        "consumer_visibility": config["consumer_visibility"],
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
        elif args.command == "resolve-plan":
            check_config(config, Path.cwd())
            report = resolve_publication_plan(config)
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
        elif args.command == "evaluate-scans":
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
        elif args.command == "record-preflight":
            scan_report = json.loads(args.scan.read_text(encoding="utf-8"))
            report = ReleaseGate(config).record(
                component=args.component,
                platform=args.platform,
                image_id=args.image_id,
                source_sha=args.source_sha,
                version=args.version,
                scan_report=scan_report,
            )
            write_report(args.report, report)
        elif args.command == "verify-gate":
            report = ReleaseGate(config).verify(
                evidence_root=args.evidence_root,
                selection=args.selection,
                source_sha=args.source_sha,
                version=args.version,
            )
            write_report(args.report, report)
        else:
            gate_report = json.loads(args.gate.read_text(encoding="utf-8"))
            report = ReleaseGate(config).authorize(
                gate_report,
                selection=args.selection,
                source_sha=args.source_sha,
                version=args.version,
            )
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
