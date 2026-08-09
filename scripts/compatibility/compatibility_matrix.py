"""Compile strict interoperability cases into CI and documentation evidence.

Official references:
- GitHub shared matrices: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
- AWS Glue versions: https://docs.aws.amazon.com/glue/latest/dg/release-notes.html
- Amazon EMR 7.8.0: https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.compatibility.artifacts import (
    CLIENT_MATRIX_ENGLISH,
    CLIENT_MATRIX_KOREAN,
    EVIDENCE_JSON,
    MATRIX_JSON,
    RELEASE_ACCEPTANCE_ENGLISH,
    RELEASE_ACCEPTANCE_KOREAN,
)

ROOT = Path(__file__).parents[2]
DEFAULT_MANIFEST = ROOT / "contracts/compatibility-scope-policy.yaml"
DEFAULT_EVIDENCE = EVIDENCE_JSON
DEFAULT_OUTPUT = MATRIX_JSON
DEFAULT_ENGLISH = CLIENT_MATRIX_ENGLISH
DEFAULT_KOREAN = CLIENT_MATRIX_KOREAN
DEFAULT_ACCEPTANCE_ENGLISH = RELEASE_ACCEPTANCE_ENGLISH
DEFAULT_ACCEPTANCE_KOREAN = RELEASE_ACCEPTANCE_KOREAN
LOGGER = logging.getLogger("mystack.compatibility")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
DIGEST_PATTERN = re.compile(r"^(sha256|sha512):([0-9a-f]+)$")
MUTABLE_TOKENS = re.compile(r"(?:^|[/:@._-])(latest|main|master|develop)(?:$|[/:@._-])", re.I)


def _localized_evidence_path(value: str, *, korean: bool) -> str:
    if not korean or not value.endswith(".md"):
        return value
    if value.endswith(".generated.md"):
        return value.removesuffix(".generated.md") + ".ko.generated.md"
    return value.removesuffix(".md") + ".ko.md"


class ManifestError(ValueError):
    """A compatibility manifest cannot be interpreted without guessing."""


class DuplicateKeyLoader(yaml.SafeLoader):
    """YAML loader that does not silently replace duplicate keys."""


def _construct_unique_mapping(
    loader: DuplicateKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ManifestError(f"duplicate YAML key path=unknown key={key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class ManifestLoader:
    """Own YAML decoding; it has no knowledge of compilation or rendering."""

    def load(self, path: Path) -> dict[str, Any]:
        LOGGER.info("event=compatibility.manifest.load.before path=%s", path)
        try:
            loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=DuplicateKeyLoader)
        except (OSError, yaml.YAMLError) as error:
            raise ManifestError(f"cannot load manifest path={path}: {error}") from error
        if not isinstance(loaded, dict):
            raise ManifestError("manifest root must be a mapping")
        LOGGER.info("event=compatibility.manifest.load.after path=%s", path)
        return loaded


class ManifestValidator:
    """Validate references and runtime truth against repository-owned configuration."""

    TOP_FIELDS = frozenset(
        {
            "schema_version",
            "official_sources",
            "artifacts",
            "runtime_profiles",
            "runner_adapters",
            "compatibility_profiles",
            "scenario_sets",
            "lanes",
            "acceptance",
            "cases",
        }
    )
    SOURCE_FIELDS = frozenset({"title", "url"})
    ARTIFACT_FIELDS = frozenset({"kind", "name", "version", "immutable_uri", "digest", "source"})
    RUNNER_FIELDS = frozenset(
        {
            "kind",
            "command_prefix",
            "timeout_config_path",
            "allowed_runtime_kinds",
            "source",
        }
    )
    PROFILE_FIELDS = frozenset(
        {
            "client",
            "versions",
            "services",
            "runtime_kinds",
            "capabilities",
            "model_fingerprints",
            "operation_ids",
            "official_sources",
        }
    )
    SCENARIO_FIELDS = frozenset({"kind", "test_nodes", "scenario_ids"})
    LANE_FIELDS = frozenset({"release_blocking", "events", "description_en", "description_ko"})
    ACCEPTANCE_FIELDS = frozenset({"summary_en", "summary_ko", "areas", "exclusions"})
    ACCEPTANCE_AREA_FIELDS = frozenset(
        {
            "title_en",
            "title_ko",
            "claim_en",
            "claim_ko",
            "case_ids",
            "scenario_ids",
            "evidence_paths",
            "official_sources",
        }
    )
    ACCEPTANCE_EXCLUSION_FIELDS = frozenset(
        {"title_en", "title_ko", "reason_en", "reason_ko", "official_sources"}
    )
    CASE_FIELDS = frozenset(
        {
            "id",
            "title_en",
            "title_ko",
            "lane",
            "runtime_profile",
            "runner_adapter",
            "compatibility_profiles",
            "scenario_set",
            "artifacts",
            "expected_duration_minutes",
        }
    )
    RUNTIME_COMMON_FIELDS = frozenset({"kind", "python_version", "source"})
    RUNTIME_FIELDS: ClassVar[dict[str, frozenset[str]]] = {
        "python": RUNTIME_COMMON_FIELDS,
        "emr": RUNTIME_COMMON_FIELDS
        | frozenset(
            {
                "java_version",
                "spark_version",
                "release_label",
                "aws_spark_version",
                "config_profile",
            }
        ),
        "glue": RUNTIME_COMMON_FIELDS
        | frozenset(
            {
                "java_version",
                "spark_version",
                "glue_version",
                "iceberg_version",
                "config_profile",
            }
        ),
    }
    RUNNER_KINDS = frozenset({"pytest", "docker-pytest"})
    ARTIFACT_KINDS = frozenset({"python-wheel", "archive", "oci-image"})
    SCENARIO_KINDS = frozenset({"contract", "e2e"})

    def __init__(self, *, root: Path = ROOT) -> None:
        self._root = root
        self._config = self._read_yaml(root / "config/runtime/mystack.yaml")
        self._models = self._read_json(root / "contracts/service-model-manifest.json")
        self._lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))

    def validate(self, document: dict[str, Any]) -> None:
        LOGGER.info("event=compatibility.manifest.validate.before")
        self._strict(document, self.TOP_FIELDS, self.TOP_FIELDS, "root")
        if document["schema_version"] != 1:
            raise ManifestError("unsupported schema_version; fix_hint=use-1")
        sources = self._id_mapping(document, "official_sources")
        artifacts = self._id_mapping(document, "artifacts")
        runtimes = self._id_mapping(document, "runtime_profiles")
        runners = self._id_mapping(document, "runner_adapters")
        profiles = self._id_mapping(document, "compatibility_profiles")
        scenarios = self._id_mapping(document, "scenario_sets")
        lanes = self._id_mapping(document, "lanes")
        self._validate_sources(sources)
        self._validate_artifacts(artifacts, sources)
        self._validate_runtimes(runtimes, sources)
        self._validate_runners(runners, sources)
        self._validate_profiles(profiles, sources)
        self._validate_scenarios(scenarios)
        self._validate_lanes(lanes)
        self._validate_cases(
            document["cases"], artifacts, runtimes, runners, profiles, scenarios, lanes
        )
        self._validate_acceptance(
            document["acceptance"],
            document["cases"],
            scenarios,
            lanes,
            sources,
        )
        LOGGER.info("event=compatibility.manifest.validate.after cases=%d", len(document["cases"]))

    def _validate_sources(self, sources: dict[str, Any]) -> None:
        for source_id, source in sources.items():
            path = f"official_sources.{source_id}"
            self._strict(source, self.SOURCE_FIELDS, self.SOURCE_FIELDS, path)
            if not source["url"].startswith("https://"):
                raise ManifestError(f"official source must use HTTPS path={path}.url")

    def _validate_artifacts(self, artifacts: dict[str, Any], sources: dict[str, Any]) -> None:
        for artifact_id, artifact in artifacts.items():
            path = f"artifacts.{artifact_id}"
            self._strict(artifact, self.ARTIFACT_FIELDS, self.ARTIFACT_FIELDS, path)
            if artifact["kind"] not in self.ARTIFACT_KINDS:
                raise ManifestError(f"unknown artifact kind path={path}.kind")
            self._reference(artifact["source"], sources, f"{path}.source")
            version = self._text(artifact["version"], f"{path}.version")
            uri = self._text(artifact["immutable_uri"], f"{path}.immutable_uri")
            if version not in uri or MUTABLE_TOKENS.search(uri):
                raise ManifestError(
                    f"mutable or unversioned artifact path={path}.immutable_uri "
                    "fix_hint=pin-version-and-content-digest"
                )
            match = DIGEST_PATTERN.fullmatch(self._text(artifact["digest"], f"{path}.digest"))
            if match is None or len(match.group(2)) != {"sha256": 64, "sha512": 128}.get(
                match.group(1) if match else "", 0
            ):
                raise ManifestError(f"invalid artifact digest path={path}.digest")
            if artifact["kind"] == "oci-image" and artifact["digest"] not in uri:
                raise ManifestError(f"OCI URI is not digest pinned path={path}.immutable_uri")
            if artifact["kind"] == "python-wheel":
                self._validate_locked_python_artifact(path, artifact)
            elif artifact["kind"] == "oci-image":
                dockerfiles = "\n".join(
                    candidate.read_text(encoding="utf-8")
                    for candidate in self._root.glob("*/Dockerfile")
                )
                if uri not in dockerfiles:
                    raise ManifestError(
                        f"OCI artifact is not used by a Dockerfile path={path}.immutable_uri"
                    )

    def _validate_runtimes(self, runtimes: dict[str, Any], sources: dict[str, Any]) -> None:
        for runtime_id, runtime in runtimes.items():
            path = f"runtime_profiles.{runtime_id}"
            kind = runtime.get("kind")
            if kind not in self.RUNTIME_FIELDS:
                raise ManifestError(f"unknown runtime kind path={path}.kind")
            self._strict(runtime, self.RUNTIME_FIELDS[kind], self.RUNTIME_FIELDS[kind], path)
            self._reference(runtime["source"], sources, f"{path}.source")
            if kind == "emr":
                release = runtime["release_label"]
                configured = self._config["emr"]["release_profiles"].get(release)
                if configured is None:
                    raise ManifestError(f"unknown configured EMR release path={path}.release_label")
                expected_profile = configured["runtime_profile"]
                base = self._config["runtime_profiles"][expected_profile]
                expected = {
                    "config_profile": expected_profile,
                    "spark_version": base["spark_version"],
                    "python_version": base["python_version"],
                    "java_version": base["java_version"],
                    "aws_spark_version": configured["aws_spark_version"],
                }
                self._exact_runtime(path, runtime, expected)
            elif kind == "glue":
                expected_profile = self._config["glue"]["runtime_profile"]
                base = self._config["runtime_profiles"][expected_profile]
                expected = {
                    "config_profile": expected_profile,
                    "glue_version": expected_profile.removeprefix("glue-"),
                    "spark_version": base["spark_version"],
                    "python_version": base["python_version"],
                    "java_version": base["java_version"],
                    "iceberg_version": base["iceberg_version"],
                }
                self._exact_runtime(path, runtime, expected)

    def _validate_runners(self, runners: dict[str, Any], sources: dict[str, Any]) -> None:
        for runner_id, runner in runners.items():
            path = f"runner_adapters.{runner_id}"
            self._strict(runner, self.RUNNER_FIELDS, self.RUNNER_FIELDS, path)
            if runner["kind"] not in self.RUNNER_KINDS:
                raise ManifestError(f"unknown runner adapter kind path={path}.kind")
            if runner["command_prefix"] != ["uv", "run", "pytest"]:
                raise ManifestError(f"unapproved command prefix path={path}.command_prefix")
            allowed = self._string_list(
                runner["allowed_runtime_kinds"], f"{path}.allowed_runtime_kinds"
            )
            if not allowed or not set(allowed) <= set(self.RUNTIME_FIELDS):
                raise ManifestError(
                    f"invalid allowed runtime kinds path={path}.allowed_runtime_kinds"
                )
            if not str(runner["timeout_config_path"]).startswith("tests."):
                raise ManifestError(
                    f"timeout must come from tests config path={path}.timeout_config_path"
                )
            self._reference(runner["source"], sources, f"{path}.source")

    def _validate_profiles(self, profiles: dict[str, Any], sources: dict[str, Any]) -> None:
        model_services = self._models["services"]
        for profile_id, profile in profiles.items():
            path = f"compatibility_profiles.{profile_id}"
            self._strict(profile, self.PROFILE_FIELDS, self.PROFILE_FIELDS, path)
            self._string_list(profile["services"], f"{path}.services")
            runtime_kinds = self._string_list(profile["runtime_kinds"], f"{path}.runtime_kinds")
            if not set(runtime_kinds) <= set(self.RUNTIME_FIELDS):
                raise ManifestError(f"unknown runtime kind path={path}.runtime_kinds")
            for source in self._string_list(
                profile["official_sources"], f"{path}.official_sources"
            ):
                self._reference(source, sources, f"{path}.official_sources")
            fingerprints = self._mapping(
                profile["model_fingerprints"], f"{path}.model_fingerprints"
            )
            operations = self._mapping(profile["operation_ids"], f"{path}.operation_ids")
            for service, fingerprint in fingerprints.items():
                if service not in model_services:
                    raise ManifestError(
                        f"unknown model service path={path}.model_fingerprints.{service}"
                    )
                if fingerprint != model_services[service]["model_fingerprint"]:
                    raise ManifestError(
                        f"model fingerprint drift path={path}.model_fingerprints.{service} "
                        "fix_hint=update-protocol-contracts-before-manifest"
                    )
            for service, names in operations.items():
                if service not in model_services:
                    raise ManifestError(
                        f"unknown operation service path={path}.operation_ids.{service}"
                    )
                known = model_services[service]["operation_fingerprints"]
                unknown = sorted(
                    set(self._string_list(names, f"{path}.operation_ids.{service}")) - set(known)
                )
                if unknown:
                    raise ManifestError(
                        f"unknown operations path={path}.operation_ids.{service} ids={unknown}"
                    )

    def _validate_scenarios(self, scenarios: dict[str, Any]) -> None:
        for scenario_id, scenario in scenarios.items():
            path = f"scenario_sets.{scenario_id}"
            self._strict(scenario, self.SCENARIO_FIELDS, self.SCENARIO_FIELDS, path)
            if scenario["kind"] not in self.SCENARIO_KINDS:
                raise ManifestError(f"unknown scenario kind path={path}.kind")
            nodes = self._string_list(scenario["test_nodes"], f"{path}.test_nodes")
            self._string_list(scenario["scenario_ids"], f"{path}.scenario_ids")
            for node in nodes:
                file_part = node.split("::", maxsplit=1)[0]
                if not (self._root / file_part).is_file():
                    raise ManifestError(f"missing test node path={path}.test_nodes node={node}")

    def _validate_lanes(self, lanes: dict[str, Any]) -> None:
        if set(lanes) != {"required", "preview", "nightly"}:
            raise ManifestError("lanes must define exactly required, preview, and nightly")
        for lane_id, lane in lanes.items():
            path = f"lanes.{lane_id}"
            self._strict(lane, self.LANE_FIELDS, self.LANE_FIELDS, path)
            if not isinstance(lane["release_blocking"], bool):
                raise ManifestError(f"release_blocking must be boolean path={path}")
            self._string_list(lane["events"], f"{path}.events")
        if lanes["required"]["release_blocking"] is not True:
            raise ManifestError("required lane must be release blocking")
        if any(lanes[name]["release_blocking"] for name in ("preview", "nightly")):
            raise ManifestError("preview and nightly lanes must be non-blocking")

    def _validate_cases(
        self,
        cases: Any,
        artifacts: dict[str, Any],
        runtimes: dict[str, Any],
        runners: dict[str, Any],
        profiles: dict[str, Any],
        scenarios: dict[str, Any],
        lanes: dict[str, Any],
    ) -> None:
        if not isinstance(cases, list) or not cases:
            raise ManifestError("cases must be a non-empty list")
        seen: set[str] = set()
        for index, case in enumerate(cases):
            path = f"cases[{index}]"
            self._strict(case, self.CASE_FIELDS, self.CASE_FIELDS, path)
            case_id = self._text(case["id"], f"{path}.id")
            if case_id in seen:
                raise ManifestError(f"duplicate case id path={path}.id id={case_id}")
            if not ID_PATTERN.fullmatch(case_id):
                raise ManifestError(f"invalid case id path={path}.id id={case_id}")
            seen.add(case_id)
            lane = self._reference(case["lane"], lanes, f"{path}.lane")
            runtime = self._reference(case["runtime_profile"], runtimes, f"{path}.runtime_profile")
            runner = self._reference(case["runner_adapter"], runners, f"{path}.runner_adapter")
            scenario = self._reference(case["scenario_set"], scenarios, f"{path}.scenario_set")
            selected_profiles = self._string_list(
                case["compatibility_profiles"], f"{path}.compatibility_profiles"
            )
            selected_artifacts = self._string_list(case["artifacts"], f"{path}.artifacts")
            for profile_id in selected_profiles:
                profile = self._reference(profile_id, profiles, f"{path}.compatibility_profiles")
                if runtime["kind"] not in profile["runtime_kinds"]:
                    raise ManifestError(
                        f"invalid runtime/profile combination path={path} profile={profile_id}"
                    )
            for artifact_id in selected_artifacts:
                self._reference(artifact_id, artifacts, f"{path}.artifacts")
            self._validate_case_versions(
                path,
                selected_profiles,
                selected_artifacts,
                profiles,
                artifacts,
            )
            if runtime["kind"] not in runner["allowed_runtime_kinds"]:
                raise ManifestError(f"invalid runtime/runner combination path={path}")
            expected_scenario = "contract" if runner["kind"] == "pytest" else "e2e"
            if scenario["kind"] != expected_scenario:
                raise ManifestError(f"invalid scenario/runner combination path={path}")
            duration = case["expected_duration_minutes"]
            if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                raise ManifestError(f"duration must be a positive integer path={path}")
            if lane["release_blocking"] and case["lane"] != "required":
                raise ManifestError(f"invalid release-blocking lane path={path}.lane")

    def _validate_acceptance(
        self,
        acceptance: Any,
        cases: list[dict[str, Any]],
        scenarios: dict[str, Any],
        lanes: dict[str, Any],
        sources: dict[str, Any],
    ) -> None:
        path = "acceptance"
        LOGGER.info("event=compatibility.acceptance.validate.before")
        self._strict(acceptance, self.ACCEPTANCE_FIELDS, self.ACCEPTANCE_FIELDS, path)
        self._text(acceptance["summary_en"], f"{path}.summary_en")
        self._text(acceptance["summary_ko"], f"{path}.summary_ko")
        areas = self._id_mapping(acceptance, "areas")
        exclusions = self._id_mapping(acceptance, "exclusions")
        case_by_id = {case["id"]: case for case in cases}
        required_case_ids = {
            case["id"] for case in cases if lanes[case["lane"]]["release_blocking"]
        }
        required_scenario_ids = {
            scenario_id
            for case in cases
            if case["id"] in required_case_ids
            for scenario_id in scenarios[case["scenario_set"]]["scenario_ids"]
        }
        covered_cases: set[str] = set()
        covered_scenarios: set[str] = set()
        for area_id, area in areas.items():
            area_path = f"{path}.areas.{area_id}"
            self._strict(
                area,
                self.ACCEPTANCE_AREA_FIELDS,
                self.ACCEPTANCE_AREA_FIELDS,
                area_path,
            )
            for field in ("title_en", "title_ko", "claim_en", "claim_ko"):
                self._text(area[field], f"{area_path}.{field}")
            area_case_ids = self._string_list(area["case_ids"], f"{area_path}.case_ids")
            area_scenario_ids = self._string_list(area["scenario_ids"], f"{area_path}.scenario_ids")
            for case_id in area_case_ids:
                case = self._reference(case_id, case_by_id, f"{area_path}.case_ids")
                if not lanes[case["lane"]]["release_blocking"]:
                    raise ManifestError(
                        f"acceptance references non-blocking case path={area_path}.case_ids "
                        f"case={case_id}"
                    )
            allowed_scenarios = {
                scenario_id
                for case_id in area_case_ids
                for scenario_id in scenarios[case_by_id[case_id]["scenario_set"]]["scenario_ids"]
            }
            unknown_scenarios = sorted(set(area_scenario_ids) - allowed_scenarios)
            if unknown_scenarios:
                raise ManifestError(
                    f"acceptance scenario is not owned by its cases path={area_path}.scenario_ids "
                    f"ids={unknown_scenarios}"
                )
            repeated_scenarios = sorted(covered_scenarios & set(area_scenario_ids))
            if repeated_scenarios:
                raise ManifestError(
                    f"acceptance scenario has multiple owners path={area_path}.scenario_ids "
                    f"ids={repeated_scenarios}"
                )
            covered_cases.update(area_case_ids)
            covered_scenarios.update(area_scenario_ids)
            for evidence_path in self._string_list(
                area["evidence_paths"], f"{area_path}.evidence_paths"
            ):
                self._validate_evidence_path(evidence_path, f"{area_path}.evidence_paths")
            for source_id in self._string_list(
                area["official_sources"], f"{area_path}.official_sources"
            ):
                self._reference(source_id, sources, f"{area_path}.official_sources")
        if covered_cases != required_case_ids:
            raise ManifestError(
                "release-blocking case acceptance coverage drift "
                f"missing={sorted(required_case_ids - covered_cases)} "
                f"extra={sorted(covered_cases - required_case_ids)} "
                "fix_hint=document-required-case-in-acceptance"
            )
        if covered_scenarios != required_scenario_ids:
            raise ManifestError(
                "release-blocking scenario acceptance coverage drift "
                f"missing={sorted(required_scenario_ids - covered_scenarios)} "
                f"extra={sorted(covered_scenarios - required_scenario_ids)} "
                "fix_hint=document-required-scenario-in-acceptance"
            )
        for exclusion_id, exclusion in exclusions.items():
            exclusion_path = f"{path}.exclusions.{exclusion_id}"
            self._strict(
                exclusion,
                self.ACCEPTANCE_EXCLUSION_FIELDS,
                self.ACCEPTANCE_EXCLUSION_FIELDS,
                exclusion_path,
            )
            for field in ("title_en", "title_ko", "reason_en", "reason_ko"):
                self._text(exclusion[field], f"{exclusion_path}.{field}")
            for source_id in self._string_list(
                exclusion["official_sources"], f"{exclusion_path}.official_sources"
            ):
                self._reference(source_id, sources, f"{exclusion_path}.official_sources")
        LOGGER.info(
            "event=compatibility.acceptance.validate.after areas=%d exclusions=%d "
            "required_cases=%d required_scenarios=%d",
            len(areas),
            len(exclusions),
            len(required_case_ids),
            len(required_scenario_ids),
        )

    def _validate_evidence_path(self, value: str, path: str) -> None:
        root = self._root.resolve()
        candidates = tuple(dict.fromkeys((value, _localized_evidence_path(value, korean=True))))
        for candidate in candidates:
            evidence = Path(candidate)
            resolved = (root / evidence).resolve()
            if (
                evidence.is_absolute()
                or not resolved.is_relative_to(root)
                or not resolved.is_file()
            ):
                raise ManifestError(
                    f"missing or unsafe acceptance evidence path={path} evidence={candidate!r}"
                )

    def _id_mapping(self, document: dict[str, Any], name: str) -> dict[str, Any]:
        value = self._mapping(document[name], name)
        if not value:
            raise ManifestError(f"mapping must not be empty path={name}")
        invalid = [item for item in value if not ID_PATTERN.fullmatch(str(item))]
        if invalid:
            raise ManifestError(f"invalid identifiers path={name} ids={invalid}")
        return value

    @staticmethod
    def _strict(value: Any, allowed: frozenset[str], required: frozenset[str], path: str) -> None:
        if not isinstance(value, dict):
            raise ManifestError(f"expected mapping path={path}")
        unknown = sorted(set(value) - allowed)
        missing = sorted(required - set(value))
        if unknown or missing:
            raise ManifestError(f"schema mismatch path={path} unknown={unknown} missing={missing}")

    @staticmethod
    def _mapping(value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ManifestError(f"expected mapping path={path}")
        return value

    @staticmethod
    def _text(value: Any, path: str) -> str:
        if not isinstance(value, str) or not value:
            raise ManifestError(f"expected non-empty string path={path}")
        return value

    @staticmethod
    def _string_list(value: Any, path: str) -> list[str]:
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item for item in value)
            or len(value) != len(set(value))
        ):
            raise ManifestError(f"expected unique non-empty string list path={path}")
        return value

    @staticmethod
    def _reference(reference: Any, values: dict[str, Any], path: str) -> Any:
        if not isinstance(reference, str) or reference not in values:
            raise ManifestError(f"unknown reference path={path} reference={reference!r}")
        return values[reference]

    @staticmethod
    def _exact_runtime(path: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
        mismatches = {
            name: {"manifest": actual.get(name), "config": value}
            for name, value in expected.items()
            if str(actual.get(name)) != str(value)
        }
        if mismatches:
            raise ManifestError(
                f"runtime/config drift path={path} fields={sorted(mismatches)} "
                "fix_hint=update-config-or-runtime-case-together"
            )

    def _validate_locked_python_artifact(self, path: str, artifact: dict[str, Any]) -> None:
        packages = [
            package
            for package in self._lock.get("package", [])
            if package.get("name") == artifact["name"]
            and str(package.get("version")) == str(artifact["version"])
        ]
        matches = [
            wheel
            for package in packages
            for wheel in package.get("wheels", [])
            if wheel.get("url") == artifact["immutable_uri"]
            and wheel.get("hash") == artifact["digest"]
        ]
        if len(matches) != 1:
            raise ManifestError(
                f"Python artifact/uv.lock drift path={path} "
                "fix_hint=lock-exact-version-before-generating-matrix"
            )

    @staticmethod
    def _validate_case_versions(
        path: str,
        selected_profiles: list[str],
        selected_artifacts: list[str],
        profiles: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> None:
        selected = [artifacts[artifact_id] for artifact_id in selected_artifacts]
        by_name = {(artifact["name"], str(artifact["version"])) for artifact in selected}
        for profile_id in selected_profiles:
            for package in ("boto3", "botocore", "awswrangler"):
                version = profiles[profile_id]["versions"].get(package)
                if version is not None and (package, str(version)) not in by_name:
                    raise ManifestError(
                        f"profile version has no exact case artifact path={path} "
                        f"profile={profile_id} package={package} version={version}"
                    )

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ManifestError(f"expected mapping path={path}")
        return value

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ManifestError(f"expected mapping path={path}")
        return value


class MatrixCompiler:
    """Resolve validated cases without executing tests or writing files."""

    MATRIX_KEYS = tuple(
        f"{lane}_{kind}"
        for lane in ("required", "preview", "nightly")
        for kind in ("contract", "e2e")
    )

    def compile(self, document: dict[str, Any]) -> dict[str, Any]:
        LOGGER.info("event=compatibility.compile.before cases=%d", len(document["cases"]))
        matrices = {key: {"include": []} for key in self.MATRIX_KEYS}
        compiled_cases: list[dict[str, Any]] = []
        for case in sorted(document["cases"], key=lambda item: item["id"]):
            resolved = self._resolve_case(document, case)
            compiled_cases.append(resolved)
            key = f"{case['lane']}_{resolved['scenario']['kind']}"
            matrices[key]["include"].append(
                {
                    "case_id": case["id"],
                    "evidence_sha256": resolved["evidence_sha256"],
                    "python_version": resolved["runtime"]["python_version"],
                    "timeout_minutes": case["expected_duration_minutes"],
                }
            )
        source_digest = self._digest(document)
        acceptance = dict(document["acceptance"])
        acceptance["evidence_sha256"] = self._digest(
            {
                "acceptance": document["acceptance"],
                "required_cases": [
                    {
                        "id": case["id"],
                        "evidence_sha256": case["evidence_sha256"],
                    }
                    for case in compiled_cases
                    if case["release_blocking"]
                ],
            }
        )
        LOGGER.info(
            "event=compatibility.acceptance.compile.after evidence_sha256=%s",
            acceptance["evidence_sha256"],
        )
        result = {
            "schema_version": 1,
            "generated_from": "deprecated manifest compiler",
            "source_sha256": source_digest,
            "lanes": document["lanes"],
            "official_sources": document["official_sources"],
            "acceptance": acceptance,
            "github_matrices": matrices,
            "cases": compiled_cases,
            "fix_hints": [
                "Client drift: add a typed pytest compatibility annotation.",
                (
                    "Protocol drift: update the owning adapter and modeled-error tests before "
                    "the model fingerprint."
                ),
                (
                    "Runtime drift: update config/runtime/mystack.yaml, the Dockerfile lock, "
                    "and the matching runtime profile together."
                ),
                (
                    "Scenario drift: update only the named scenario set; do not create an "
                    "implicit version cross-product."
                ),
            ],
        }
        LOGGER.info("event=compatibility.compile.after source_sha256=%s", source_digest)
        return result

    def _resolve_case(self, document: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        resolved = {
            "id": case["id"],
            "title_en": case["title_en"],
            "title_ko": case["title_ko"],
            "lane": case["lane"],
            "release_blocking": document["lanes"][case["lane"]]["release_blocking"],
            "expected_duration_minutes": case["expected_duration_minutes"],
            "runtime_profile_id": case["runtime_profile"],
            "runtime": document["runtime_profiles"][case["runtime_profile"]],
            "runner_adapter_id": case["runner_adapter"],
            "runner": document["runner_adapters"][case["runner_adapter"]],
            "scenario_set_id": case["scenario_set"],
            "scenario": document["scenario_sets"][case["scenario_set"]],
            "compatibility_profile_ids": case["compatibility_profiles"],
            "compatibility_profiles": {
                name: document["compatibility_profiles"][name]
                for name in case["compatibility_profiles"]
            },
            "artifact_ids": case["artifacts"],
            "artifacts": {name: document["artifacts"][name] for name in case["artifacts"]},
        }
        resolved["evidence_sha256"] = self._digest(resolved)
        return resolved

    @staticmethod
    def _digest(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class MatrixRenderer:
    """Render the same compiled evidence for English and Korean readers."""

    def render(self, compiled: dict[str, Any], *, korean: bool) -> str:
        if korean:
            title = "# 생성된 Client 호환성 Matrix"
            intro = (
                "이 파일은 주석 pytest 증거와 "
                "`contracts/compatibility-scope-policy.yaml`에서 생성됩니다. "
                "직접 수정하지 마세요. 각 행은 CI가 독립 process에서 실행하는 명시적 "
                "조합이며 지원하지 않는 전수 조합을 뜻하지 않습니다."
            )
            headings = (
                "| Case | 실행 구분 | Runtime | 고정 버전 | Scenario | Evidence |\n"
                "| --- | --- | --- | --- | --- | --- |"
            )
            policy = "## 실행 구분 정책"
            source_heading = "## 공식 참고 자료"
            cases_heading = "## 호환성 Case"
            toc_title = "목차"
            toc_entries = (
                "- [호환성 Case](#호환성-case)",
                "- [실행 구분 정책](#실행-구분-정책)",
                "- [공식 참고 자료](#공식-참고-자료)",
            )
        else:
            title = "# Generated client compatibility matrix"
            intro = (
                "This file is deterministically generated from annotated pytest evidence and "
                "`contracts/compatibility-scope-policy.yaml`; "
                "do not edit it. Each row is one explicit combination run by CI in an "
                "isolated process, not an unsupported cross-product."
            )
            headings = (
                "| Case | Lane | Runtime | Exact versions | Scenarios | Evidence |\n"
                "| --- | --- | --- | --- | --- | --- |"
            )
            policy = "## Lane policy"
            source_heading = "## Official sources"
            cases_heading = "## Compatibility cases"
            toc_title = "Contents"
            toc_entries = (
                "- [Compatibility cases](#compatibility-cases)",
                "- [Lane policy](#lane-policy)",
                "- [Official sources](#official-sources)",
            )
        lines = [
            title,
            "",
            "<!-- toc:start -->",
            f"## {toc_title}",
            "",
            *toc_entries,
            "<!-- toc:end -->",
            "",
            intro,
            "",
            cases_heading,
            "",
            headings,
        ]
        for case in compiled["cases"]:
            versions: dict[str, str] = {}
            for profile in case["compatibility_profiles"].values():
                versions.update({name: str(value) for name, value in profile["versions"].items()})
            version_text = ", ".join(f"{name} {value}" for name, value in sorted(versions.items()))
            scenarios = ", ".join(case["scenario"]["scenario_ids"])
            lines.append(
                f"| `{case['id']}` | `{case['lane']}` | `{case['runtime_profile_id']}` | "
                f"{version_text} | {scenarios} | `{case['evidence_sha256'][:16]}` |"
            )
        lines.extend(["", policy, ""])
        for lane_id in ("required", "preview", "nightly"):
            lane = compiled["lanes"][lane_id]
            description = lane["description_ko" if korean else "description_en"]
            release_blocking = str(lane["release_blocking"]).lower()
            lines.append(f"- `{lane_id}`: {description}; release_blocking=`{release_blocking}`")
        lines.extend(["", source_heading, ""])
        for source_id, source in sorted(compiled["official_sources"].items()):
            lines.append(f"- [{source['title']}]({source['url']}) (`{source_id}`)")
        return "\n".join(lines) + "\n"


class AcceptanceRenderer:
    """Render release-blocking scope and evidence from the same validated manifest."""

    def render(self, compiled: dict[str, Any], *, korean: bool) -> str:
        acceptance = compiled["acceptance"]
        if korean:
            counterpart = "release-acceptance.generated.md"
            counterpart_label = "English"
            title = "# Catalog release 수용 범위 (생성됨)"
            intro = (
                "이 파일은 주석 pytest 증거와 "
                "`contracts/compatibility-scope-policy.yaml`에서 생성됩니다. 직접 수정하지 "
                "마세요. 아래 모든 case는 `required`이며 release 게시 전에 통과해야 합니다."
            )
            area_heading = "## Release-blocking 보장"
            headings = ("영역", "보장", "Case", "고정 버전", "Scenario", "근거", "공식 출처")
            exclusion_heading = "## 명시적 제외"
            exclusion_headings = ("영역", "제외 이유", "공식 출처")
            source_heading = "## 공식 참고 자료"
            summary = acceptance["summary_ko"]
            evidence_label = "수용 근거"
            toc_title = "목차"
            toc_entries = (
                "- [Release-blocking 보장](#release-blocking-보장)",
                "- [명시적 제외](#명시적-제외)",
                "- [공식 참고 자료](#공식-참고-자료)",
            )
        else:
            counterpart = "release-acceptance.ko.generated.md"
            counterpart_label = "한국어"
            title = "# Catalog release acceptance (generated)"
            intro = (
                "This file is deterministically generated from annotated pytest evidence and "
                "`contracts/compatibility-scope-policy.yaml`; do not "
                "edit it directly. Every case below is `required` and must pass before publication."
            )
            area_heading = "## Release-blocking guarantees"
            headings = (
                "Area",
                "Claim",
                "Cases",
                "Exact versions",
                "Scenarios",
                "Evidence",
                "Official sources",
            )
            exclusion_heading = "## Explicit exclusions"
            exclusion_headings = ("Area", "Reason", "Official sources")
            source_heading = "## Official references"
            summary = acceptance["summary_en"]
            evidence_label = "Acceptance evidence"
            toc_title = "Contents"
            toc_entries = (
                "- [Release-blocking guarantees](#release-blocking-guarantees)",
                "- [Explicit exclusions](#explicit-exclusions)",
                "- [Official references](#official-references)",
            )
        lines = [
            f"[{counterpart_label}]({counterpart})",
            "",
            title,
            "",
            "<!-- toc:start -->",
            f"## {toc_title}",
            "",
            *toc_entries,
            "<!-- toc:end -->",
            "",
            intro,
            "",
            summary,
            "",
            f"{evidence_label}: `{acceptance['evidence_sha256']}`",
            "",
            area_heading,
            "",
            "| " + " | ".join(headings) + " |",
            "| " + " | ".join("---" for _ in headings) + " |",
        ]
        referenced_sources: set[str] = set()
        case_by_id = {case["id"]: case for case in compiled["cases"]}
        for area_id, area in acceptance["areas"].items():
            referenced_sources.update(area["official_sources"])
            title_text = area["title_ko" if korean else "title_en"]
            claim = area["claim_ko" if korean else "claim_en"]
            cases = "<br>".join(f"`{value}`" for value in area["case_ids"])
            versions = {
                name: str(version)
                for case_id in area["case_ids"]
                for profile in case_by_id[case_id]["compatibility_profiles"].values()
                for name, version in profile["versions"].items()
            }
            version_text = "<br>".join(
                f"{name} `{version}`" for name, version in sorted(versions.items())
            )
            scenarios = "<br>".join(f"`{value}`" for value in area["scenario_ids"])
            evidence = "<br>".join(
                f"[{_localized_evidence_path(value, korean=korean)}]"
                f"(../../{_localized_evidence_path(value, korean=korean)})"
                for value in area["evidence_paths"]
            )
            sources = "<br>".join(
                f"[{value}]({compiled['official_sources'][value]['url']})"
                for value in area["official_sources"]
            )
            lines.append(
                f"| `{area_id}` — {title_text} | {claim} | {cases} | {version_text} | "
                f"{scenarios} | {evidence} | {sources} |"
            )
        lines.extend(
            [
                "",
                exclusion_heading,
                "",
                "| " + " | ".join(exclusion_headings) + " |",
                "| " + " | ".join("---" for _ in exclusion_headings) + " |",
            ]
        )
        for exclusion_id, exclusion in acceptance["exclusions"].items():
            referenced_sources.update(exclusion["official_sources"])
            title_text = exclusion["title_ko" if korean else "title_en"]
            reason = exclusion["reason_ko" if korean else "reason_en"]
            sources = "<br>".join(
                f"[{value}]({compiled['official_sources'][value]['url']})"
                for value in exclusion["official_sources"]
            )
            lines.append(f"| `{exclusion_id}` — {title_text} | {reason} | {sources} |")
        lines.extend(["", source_heading, ""])
        for source_id in sorted(referenced_sources):
            source = compiled["official_sources"][source_id]
            lines.append(f"- [{source['title']}]({source['url']}) (`{source_id}`)")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class GeneratedArtifacts:
    """Own comparison and atomic writes for compiler outputs."""

    output: Path
    english: Path
    korean: Path
    acceptance_english: Path
    acceptance_korean: Path

    def expected(
        self,
        compiled: dict[str, Any],
        renderer: MatrixRenderer,
        acceptance_renderer: AcceptanceRenderer,
    ) -> dict[Path, str]:
        return {
            self.output: json.dumps(compiled, indent=2, sort_keys=True) + "\n",
            self.english: renderer.render(compiled, korean=False),
            self.korean: renderer.render(compiled, korean=True),
            self.acceptance_english: acceptance_renderer.render(compiled, korean=False),
            self.acceptance_korean: acceptance_renderer.render(compiled, korean=True),
        }

    def check(self, expected: dict[Path, str]) -> None:
        drifted = [path for path, content in expected.items() if self._read(path) != content]
        if drifted:
            joined = ",".join(str(path) for path in drifted)
            LOGGER.error(
                "event=compatibility.generated.check.failed paths=%s "
                "fix_hint=run-make-compatibility-generate",
                joined,
            )
            raise ManifestError(f"generated compatibility evidence drift paths={joined}")
        LOGGER.info("event=compatibility.generated.check.after files=%d drift=false", len(expected))

    def write(self, expected: dict[Path, str]) -> None:
        for path, content in expected.items():
            LOGGER.info("event=compatibility.generated.write.before path=%s", path)
            path.parent.mkdir(parents=True, exist_ok=True)
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
            LOGGER.info(
                "event=compatibility.generated.write.after path=%s bytes=%d", path, len(content)
            )

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None


def compile_manifest(
    path: Path, *, root: Path = ROOT, evidence_path: Path = DEFAULT_EVIDENCE
) -> dict[str, Any]:
    """Combine resolved pytest evidence with the small, human-owned scope policy."""

    policy = ManifestLoader().load(path)
    allowed = {
        "schema_version",
        "official_sources",
        "lanes",
        "acceptance",
        "not_planned_operation_families",
    }
    if set(policy) != allowed or policy.get("schema_version") != 1:
        raise ManifestError("scope policy schema mismatch")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
        raise ManifestError("annotated evidence schema mismatch")
    cases, matrices = evidence.get("cases"), evidence.get("github_matrices")
    if not isinstance(cases, list) or not cases or not isinstance(matrices, dict):
        raise ManifestError("annotated evidence must contain non-empty cases and GitHub matrices")
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(cases) or len(set(case_ids)) != len(case_ids):
        raise ManifestError("annotated evidence contains missing or duplicate case id")
    lanes = policy["lanes"]
    if not isinstance(lanes, dict) or set(lanes) != {"required", "preview", "nightly"}:
        raise ManifestError("scope policy must define required, preview, and nightly lanes")
    for case in cases:
        lane, scenario = case.get("lane"), case.get("scenario")
        if lane not in lanes or case.get("release_blocking") is not lanes[lane].get(
            "release_blocking"
        ):
            raise ManifestError(f"annotated case lane/release policy drift case={case.get('id')}")
        if (
            not isinstance(scenario, dict)
            or not scenario.get("scenario_ids")
            or not case.get("test_nodes")
        ):
            raise ManifestError(
                f"annotated case lacks resolved scenario or test nodes case={case.get('id')}"
            )
    acceptance, sources = policy["acceptance"], policy["official_sources"]
    if not isinstance(acceptance, dict) or not isinstance(acceptance.get("areas"), dict):
        raise ManifestError("scope policy acceptance areas must be a mapping")
    required_cases = {case["id"] for case in cases if case["release_blocking"]}
    required_scenarios = {
        scenario_id
        for case in cases
        if case["release_blocking"]
        for scenario_id in case["scenario"]["scenario_ids"]
    }
    covered_cases: set[str] = set()
    covered_scenarios: set[str] = set()
    for area_id, area in acceptance["areas"].items():
        if not isinstance(area, dict):
            raise ManifestError(f"acceptance area must be a mapping area={area_id}")
        covered_cases.update(area.get("case_ids", []))
        covered_scenarios.update(area.get("scenario_ids", []))
        for source in area.get("official_sources", []):
            if source not in sources:
                raise ManifestError(f"unknown acceptance source area={area_id} source={source}")
        for evidence_file in area.get("evidence_paths", []):
            if not isinstance(evidence_file, str) or not (root / evidence_file).is_file():
                raise ManifestError(f"missing or unsafe acceptance evidence area={area_id}")
    if covered_cases != required_cases or covered_scenarios != required_scenarios:
        raise ManifestError("scenario acceptance coverage drift")
    for exclusion_id, exclusion in acceptance.get("exclusions", {}).items():
        for source in exclusion.get("official_sources", []):
            if source not in sources:
                raise ManifestError(
                    f"unknown exclusion source exclusion={exclusion_id} source={source}"
                )
    digest = MatrixCompiler._digest(
        {"policy": policy, "annotated_evidence_sha256": evidence.get("source_sha256")}
    )
    compiled_acceptance = dict(acceptance)
    compiled_acceptance["evidence_sha256"] = MatrixCompiler._digest(
        {
            "acceptance": acceptance,
            "required_cases": [
                {"id": case["id"], "evidence_sha256": case["evidence_sha256"]}
                for case in cases
                if case["release_blocking"]
            ],
        }
    )
    return {
        "schema_version": 1,
        "generated_from": {
            "annotated_evidence": evidence_path.resolve().relative_to(root.resolve()).as_posix(),
            "scope_policy": path.resolve().relative_to(root.resolve()).as_posix(),
        },
        "source_sha256": digest,
        "lanes": lanes,
        "official_sources": sources,
        "acceptance": compiled_acceptance,
        "github_matrices": matrices,
        "cases": sorted(cases, key=lambda value: value["id"]),
        "fix_hints": [
            "Case drift: add or update a typed pytest compatibility annotation.",
            "Scope drift: update only the explicit compatibility-scope policy.",
            "Operation drift: update implementation inventory or NOT_PLANNED policy.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--english", type=Path, default=DEFAULT_ENGLISH)
    parser.add_argument("--korean", type=Path, default=DEFAULT_KOREAN)
    parser.add_argument("--acceptance-english", type=Path, default=DEFAULT_ACCEPTANCE_ENGLISH)
    parser.add_argument("--acceptance-korean", type=Path, default=DEFAULT_ACCEPTANCE_KOREAN)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    action.add_argument("--github-matrix", choices=MatrixCompiler.MATRIX_KEYS)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = parse_args()
    if args.github_matrix:
        LOGGER.info(
            "event=compatibility.github_matrix.read.before path=%s key=%s",
            args.output,
            args.github_matrix,
        )
        generated = json.loads(args.output.read_text(encoding="utf-8"))
        print(json.dumps(generated["github_matrices"][args.github_matrix], separators=(",", ":")))
        LOGGER.info("event=compatibility.github_matrix.read.after key=%s", args.github_matrix)
        return
    try:
        compiled = compile_manifest(args.manifest, evidence_path=args.evidence)
        artifacts = GeneratedArtifacts(
            args.output,
            args.english,
            args.korean,
            args.acceptance_english,
            args.acceptance_korean,
        )
        expected = artifacts.expected(compiled, MatrixRenderer(), AcceptanceRenderer())
        if args.write:
            artifacts.write(expected)
        else:
            artifacts.check(expected)
    except ManifestError as error:
        LOGGER.error("event=compatibility.failed error=%s", error)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
