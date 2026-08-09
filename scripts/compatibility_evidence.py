"""Compile typed pytest compatibility annotations into deterministic CI evidence.

The compiler invokes pytest in ``--collect-only`` mode, so generation resolves real node IDs and
markers without executing test bodies, fixtures, Docker Compose, or external clients.

References:
- https://docs.pytest.org/en/stable/how-to/usage.html
- https://docs.pytest.org/en/stable/how-to/mark.html
- https://docs.pytest.org/en/stable/how-to/plugins.html#disabling-plugin-autoloading
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from mystack.aws_protocol import ConfigurationError, load_configuration

try:
    from scripts.operation_inventory import (
        OperationInventoryError,
        extract_implemented_operation_inventory,
    )
except ModuleNotFoundError:  # Direct ``python scripts/compatibility_evidence.py`` execution.
    from operation_inventory import OperationInventoryError, extract_implemented_operation_inventory

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "contracts/compatibility-evidence.generated.json"
DEFAULT_ENGLISH = ROOT / "docs/compatibility/annotated-evidence.generated.md"
DEFAULT_KOREAN = ROOT / "docs/compatibility/annotated-evidence.ko.generated.md"
DEFAULT_SERVICE_MODEL = ROOT / "contracts/service-model-manifest.json"
DEFAULT_CONFIG = ROOT / "config/mystack.yaml"
DEFAULT_LOCK = ROOT / "uv.lock"
LOGGER = logging.getLogger("mystack.compatibility.evidence")
_PYTHON_PACKAGES = frozenset({"boto3", "botocore", "awswrangler"})
_SENSITIVE_DIAGNOSTIC_ASSIGNMENT = re.compile(
    r"(?i)\b("
    r"(?:aws_)?(?:access[_-]?key(?:[_-]?id)?|secret(?:[_-]?access[_-]?key)?|"
    r"session[_-]?token|security[_-]?token|authorization|credential|password|signature|token)"
    r")\s*([=:])\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_SENSITIVE_DIAGNOSTIC_HEADER = re.compile(
    r"(?im)\b(?P<name>proxy-authorization|authorization|x-amz-security-token)"
    r"\s*(?P<separator>[:=])\s*[^\r\n]*"
)
_SENSITIVE_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


class EvidenceCompilationError(ValueError):
    """Collected compatibility evidence cannot safely drive CI or user-facing claims."""


def _configured_config_path(config_path: Path | None = None) -> Path:
    """Resolve the same file-based configuration selection used by Make targets and services."""

    if config_path is not None:
        return config_path
    configured = os.environ.get("MYSTACK_CONFIG_FILE")
    return Path(configured) if configured else DEFAULT_CONFIG


def _collection_timeout_seconds(config_path: Path) -> float:
    """Read the collection-process deadline from the selected YAML configuration file."""

    try:
        document = load_configuration(config_path).document
    except ConfigurationError as error:
        raise EvidenceCompilationError(
            "cannot load effective compatibility collection configuration "
            f"config={config_path}: {error}"
        ) from error
    tests = _mapping(document.get("tests"), "config.tests")
    value = tests.get("compatibility_collection_timeout_seconds")
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise EvidenceCompilationError(
            "compatibility collection timeout must be a positive number "
            f"path=config.tests.compatibility_collection_timeout_seconds config={config_path}"
        )
    return float(value)


def collect_annotations(*, config_path: Path | None = None) -> dict[str, Any]:
    """Run one isolated pytest collection subprocess and load its JSON output."""

    selected_config = _configured_config_path(config_path)
    timeout_seconds = _collection_timeout_seconds(selected_config)
    with tempfile.TemporaryDirectory(prefix="mystack-compatibility-") as directory:
        output = Path(directory) / "collected.json"
        test_paths = _annotated_test_paths()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "pytest_timeout",
            "-p",
            "pytest_asyncio.plugin",
            "-p",
            "test_support.compatibility_plugin",
            "--mystack-compatibility-forbidden-import",
            "awswrangler",
            "--mystack-compatibility-forbidden-import",
            "pyarrow",
            "--mystack-compatibility-output",
            str(output),
            *test_paths,
        ]
        LOGGER.info(
            "event=compatibility.annotation_collect.before command=%s test_files=%d "
            "timeout_seconds=%s executes_tests=false",
            json.dumps(command),
            len(test_paths),
            timeout_seconds,
        )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                cwd=ROOT,
                env=_collection_environment(),
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            LOGGER.error(
                "event=compatibility.annotation_collect.timeout timeout_seconds=%s stdout_tail=%s "
                "stderr_tail=%s fix_hint=%s",
                timeout_seconds,
                _tail(error.output),
                _tail(error.stderr),
                "increase-tests.compatibility_collection_timeout_seconds-or-repair-collection-imports",
            )
            raise EvidenceCompilationError(
                "pytest compatibility collection timed out; "
                "fix_hint=inspect-annotation-imports-or-tests.compatibility_collection_timeout_seconds"
            ) from error
        if completed.returncode != 0:
            LOGGER.error(
                "event=compatibility.annotation_collect.failed returncode=%d stdout_tail=%s "
                "stderr_tail=%s",
                completed.returncode,
                _tail(completed.stdout),
                _tail(completed.stderr),
            )
            raise EvidenceCompilationError(
                "pytest compatibility collection failed; "
                "fix_hint=correct-mystack-compatibility-annotations"
            )
        if not output.is_file():
            raise EvidenceCompilationError("pytest collection completed without evidence output")
        document = _load_json(output)
        LOGGER.info(
            "event=compatibility.annotation_collect.after cases=%d executes_tests=false",
            len(document.get("cases", [])),
        )
        return document


def _collection_environment() -> dict[str, str]:
    """Limit collection to the two configured pytest plugins needed by annotated tests.

    Third-party pytest entry points can import optional client stacks during collection.  Evidence
    generation needs neither their runtime hooks nor test execution, so explicit plugin loading
    keeps this developer-facing check lightweight and repeatable.
    """

    environment = dict(os.environ)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _annotated_test_paths() -> list[str]:
    """Discover only files that declare evidence before asking pytest to resolve their node IDs.

    The AST pass is deliberately shallow and never imports test modules. It keeps collection fast on
    a workstation while retaining pytest as the authority for parametrization, marker inheritance,
    and final node IDs.
    """

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = _mapping(
        _mapping(pyproject.get("tool", {}), "pyproject.tool").get("pytest", {}),
        "pyproject.tool.pytest",
    )
    ini_options = _mapping(pytest_options.get("ini_options", {}), "pyproject.pytest.ini_options")
    test_roots = ini_options.get("testpaths")
    if not isinstance(test_roots, list) or not all(
        isinstance(path, str) and path for path in test_roots
    ):
        raise EvidenceCompilationError("pyproject pytest testpaths must be a non-empty string list")

    paths: list[str] = []
    for configured_root in test_roots:
        root = ROOT / configured_root
        if not root.is_dir():
            raise EvidenceCompilationError(f"configured pytest testpath does not exist path={root}")
        for path in sorted(root.rglob("*.py")):
            if not _is_pytest_module(path) or not _declares_compatibility_evidence(path):
                continue
            paths.append(path.relative_to(ROOT).as_posix())
    if not paths:
        raise EvidenceCompilationError("no test file declares mystack compatibility evidence")
    return paths


def _is_pytest_module(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def _declares_compatibility_evidence(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as error:
        raise EvidenceCompilationError(
            f"cannot scan compatibility test path={path}: {error}"
        ) from error
    for node in ast.walk(tree):
        for decorator in getattr(node, "decorator_list", ()):
            expression = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(expression, ast.Name) and expression.id == "compatibility_evidence":
                return True
            if isinstance(expression, ast.Attribute) and expression.attr in {
                "compatibility_evidence",
                "mystack_compatibility",
            }:
                return True
    return False


class EvidenceCompiler:
    """Pure application service that validates collected test claims and compiles CI selections."""

    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG,
        lock_path: Path = DEFAULT_LOCK,
        service_model_path: Path = DEFAULT_SERVICE_MODEL,
    ) -> None:
        self._config = _load_yaml(config_path)
        self._lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        self._service_model = _load_json(service_model_path)

    def compile(self, collected: dict[str, Any]) -> dict[str, Any]:
        """Validate primitive collection data and turn it into the runner's stable contract."""

        cases = self._validate_collection(collected)
        compiled_cases = [self._compile_case(case) for case in cases]
        compiled_cases.sort(key=lambda case: case["id"])
        self._validate_operation_evidence(compiled_cases)
        result = {
            "schema_version": 1,
            "generated_from": "pytest mystack_compatibility markers",
            "source_sha256": _digest(collected),
            "github_matrices": _matrices(compiled_cases),
            "cases": compiled_cases,
        }
        LOGGER.info(
            "event=compatibility.annotation_compile.after cases=%d source_sha256=%s",
            len(compiled_cases),
            result["source_sha256"],
        )
        return result

    def _validate_collection(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        if set(document) != {"schema_version", "generated_from", "cases"}:
            raise EvidenceCompilationError(
                "collected evidence has an unknown or missing top-level field"
            )
        if document["schema_version"] != 1:
            raise EvidenceCompilationError("unsupported collected evidence schema version")
        cases = document["cases"]
        if not isinstance(cases, list) or not cases:
            raise EvidenceCompilationError("collected evidence must contain at least one case")
        seen: set[str] = set()
        for case in cases:
            self._validate_case(case)
            case_id = case["id"]
            if case_id in seen:
                raise EvidenceCompilationError(f"duplicate collected case_id={case_id!r}")
            seen.add(case_id)
        return cases

    def _validate_case(self, case: object) -> None:
        if not isinstance(case, dict):
            raise EvidenceCompilationError("collected case must be a mapping")
        expected = {
            "id",
            "profile",
            "test_nodes",
            "scenario_ids",
            "operations",
            "capabilities",
            "support_claims",
        }
        if set(case) != expected:
            raise EvidenceCompilationError(
                f"collected case schema mismatch id={case.get('id')!r} "
                f"unknown={sorted(set(case) - expected)} missing={sorted(expected - set(case))}"
            )
        case_id = _text(case["id"], "case.id")
        profile = _mapping(case["profile"], f"case.{case_id}.profile")
        if profile.get("id") != case_id:
            raise EvidenceCompilationError(f"case/profile id mismatch case_id={case_id!r}")
        self._validate_profile(profile, case_id)
        nodes = _strings(case["test_nodes"], f"case.{case_id}.test_nodes")
        if nodes != sorted(nodes):
            raise EvidenceCompilationError(f"test nodes must be sorted case_id={case_id!r}")
        _strings(case["scenario_ids"], f"case.{case_id}.scenario_ids")
        operations = _mapping(case["operations"], f"case.{case_id}.operations")
        for service, names in operations.items():
            service_name = _text(service, f"case.{case_id}.operations service")
            operation_names = _strings(names, f"case.{case_id}.operations.{service_name}")
            model_services = _mapping(self._service_model["services"], "service_model.services")
            if service_name not in model_services:
                raise EvidenceCompilationError(
                    f"unknown operation service case_id={case_id!r} service={service_name!r}"
                )
            known = _mapping(model_services[service_name], f"service_model.services.{service_name}")
            inventory = _mapping(
                known["operation_fingerprints"],
                f"service_model.services.{service_name}.operation_fingerprints",
            )
            unknown = sorted(set(operation_names) - set(inventory))
            if unknown:
                raise EvidenceCompilationError(
                    f"unknown operations case_id={case_id!r} service={service_name!r} ids={unknown}"
                )
        _strings(case["capabilities"], f"case.{case_id}.capabilities", allow_empty=True)
        claims = _strings(case["support_claims"], f"case.{case_id}.support_claims")
        if set(claims) - {"verified", "partial"}:
            raise EvidenceCompilationError(f"unknown support claim case_id={case_id!r}")

    def _validate_profile(self, profile: dict[str, Any], case_id: str) -> None:
        expected = {
            "id",
            "title_en",
            "title_ko",
            "client",
            "versions",
            "runtime_profile",
            "runtime_kind",
            "python_version",
            "lane",
            "execution",
            "expected_duration_minutes",
            "reference_urls",
        }
        if set(profile) != expected:
            raise EvidenceCompilationError(
                f"profile schema mismatch case_id={case_id!r} "
                f"unknown={sorted(set(profile) - expected)} "
                f"missing={sorted(expected - set(profile))}"
            )
        for field in ("id", "title_en", "title_ko", "client", "runtime_profile", "python_version"):
            _text(profile[field], f"case.{case_id}.profile.{field}")
        versions = _mapping(profile["versions"], f"case.{case_id}.profile.versions")
        for package, version in versions.items():
            _text(package, f"case.{case_id}.profile.versions package")
            _text(version, f"case.{case_id}.profile.versions.{package}")
        if profile["lane"] not in {"required", "preview", "nightly"}:
            raise EvidenceCompilationError(f"unknown lane case_id={case_id!r}")
        if profile["execution"] not in {"contract", "e2e"}:
            raise EvidenceCompilationError(f"unknown execution kind case_id={case_id!r}")
        if profile["runtime_kind"] not in {"python", "emr", "glue"}:
            raise EvidenceCompilationError(f"unknown runtime kind case_id={case_id!r}")
        duration = profile["expected_duration_minutes"]
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise EvidenceCompilationError(f"invalid duration case_id={case_id!r}")
        urls = _strings(profile["reference_urls"], f"case.{case_id}.profile.reference_urls")
        if any(not url.startswith("https://") for url in urls):
            raise EvidenceCompilationError(f"profile reference must use HTTPS case_id={case_id!r}")
        self._validate_locked_versions(versions, case_id)
        self._validate_runtime(profile, case_id)

    def _validate_locked_versions(self, versions: dict[str, Any], case_id: str) -> None:
        locked = {
            str(package["name"]): str(package["version"])
            for package in self._lock.get("package", [])
            if isinstance(package, dict) and "name" in package and "version" in package
        }
        for package, version in versions.items():
            if package in _PYTHON_PACKAGES and locked.get(package) != str(version):
                raise EvidenceCompilationError(
                    f"locked client version mismatch case_id={case_id!r} "
                    f"package={package!r} declared={version!r} locked={locked.get(package)!r}"
                )

    def _validate_runtime(self, profile: dict[str, Any], case_id: str) -> None:
        versions = _mapping(profile["versions"], f"case.{case_id}.profile.versions")
        runtime_kind = profile["runtime_kind"]
        runtime_profile = profile["runtime_profile"]
        if runtime_kind == "python":
            expected = f"python-{profile['python_version']}"
            if runtime_profile != expected:
                raise EvidenceCompilationError(
                    f"python runtime profile mismatch case_id={case_id!r} expected={expected!r}"
                )
            return
        runtime_profiles = _mapping(self._config["runtime_profiles"], "config.runtime_profiles")
        if runtime_kind == "glue":
            configured = _text(
                self._config["glue"]["runtime_profile"], "config.glue.runtime_profile"
            )
            runtime = _mapping(
                runtime_profiles[configured], f"config.runtime_profiles.{configured}"
            )
            expected = f"{configured}-spark-{runtime['spark_version']}"
            if runtime_profile != expected:
                raise EvidenceCompilationError(
                    f"Glue runtime profile mismatch case_id={case_id!r} expected={expected!r}"
                )
            if "glue" in versions and versions.get("glue") != configured.removeprefix("glue-"):
                raise EvidenceCompilationError(f"Glue version/config mismatch case_id={case_id!r}")
            if "spark" in versions and str(versions.get("spark")) != str(runtime["spark_version"]):
                raise EvidenceCompilationError(f"Spark version/config mismatch case_id={case_id!r}")
            return
        release_label = f"emr-{versions.get('emr', '')}"
        releases = _mapping(self._config["emr"]["release_profiles"], "config.emr.release_profiles")
        if release_label not in releases:
            raise EvidenceCompilationError(f"unknown EMR release profile case_id={case_id!r}")
        release = _mapping(releases[release_label], f"config.emr.release_profiles.{release_label}")
        configured = _text(
            release["runtime_profile"], f"config.emr.release_profiles.{release_label}"
        )
        runtime = _mapping(runtime_profiles[configured], f"config.runtime_profiles.{configured}")
        expected = f"{release_label}-spark-{runtime['spark_version']}"
        if runtime_profile != expected:
            raise EvidenceCompilationError(
                f"EMR runtime profile mismatch case_id={case_id!r} expected={expected!r}"
            )
        if str(versions.get("spark")) != str(runtime["spark_version"]):
            raise EvidenceCompilationError(f"Spark version/config mismatch case_id={case_id!r}")

    def _compile_case(self, collected: dict[str, Any]) -> dict[str, Any]:
        profile = collected["profile"]
        execution = profile["execution"]
        runner = {
            "kind": "pytest" if execution == "contract" else "docker-pytest",
            "command_prefix": ["uv", "run", "pytest"],
            "timeout_config_path": (
                "tests.contract_timeout_seconds"
                if execution == "contract"
                else "tests.e2e_timeout_seconds"
            ),
        }
        support = "partial" if "partial" in collected["support_claims"] else "verified"
        operations = collected["operations"]
        result: dict[str, Any] = {
            "id": collected["id"],
            "title_en": profile["title_en"],
            "title_ko": profile["title_ko"],
            "lane": profile["lane"],
            "release_blocking": profile["lane"] == "required",
            "expected_duration_minutes": profile["expected_duration_minutes"],
            "runtime_profile_id": profile["runtime_profile"],
            "runtime": {
                "kind": profile["runtime_kind"],
                "python_version": profile["python_version"],
            },
            "runner_adapter_id": "pytest-contract" if execution == "contract" else "docker-e2e",
            "runner": runner,
            "scenario_set_id": collected["id"],
            "scenario": {
                "kind": execution,
                "test_nodes": collected["test_nodes"],
                "scenario_ids": collected["scenario_ids"],
            },
            "compatibility_profile_ids": [collected["id"]],
            "compatibility_profiles": {
                collected["id"]: {
                    "client": profile["client"],
                    "versions": profile["versions"],
                    "services": sorted(operations),
                    "model_fingerprints": self._model_fingerprints(operations),
                    "capabilities": collected["capabilities"],
                    "reference_urls": profile["reference_urls"],
                }
            },
            "operations": operations,
            "capabilities": collected["capabilities"],
            "support": support,
            "test_nodes": collected["test_nodes"],
        }
        result["evidence_sha256"] = _digest(result)
        return result

    def _model_fingerprints(self, operations: dict[str, Any]) -> dict[str, str]:
        """Bind annotation evidence to the pinned model for each modeled service it exercises."""

        services = _mapping(self._service_model["services"], "service_model.services")
        return {
            service: _text(
                _mapping(services[service], f"service_model.services.{service}")[
                    "model_fingerprint"
                ],
                f"service_model.services.{service}.model_fingerprint",
            )
            for service in sorted(operations)
        }

    def _validate_operation_evidence(self, compiled_cases: Iterable[dict[str, Any]]) -> None:
        evidence: dict[str, set[str]] = defaultdict(set)
        for case in compiled_cases:
            for service, names in case["operations"].items():
                evidence[service].update(names)
        try:
            code_owned = extract_implemented_operation_inventory()
        except OperationInventoryError as error:
            raise EvidenceCompilationError(
                f"cannot validate code-owned operation inventory: {error}"
            ) from error
        for service, registered in code_owned.items():
            missing = sorted(registered - evidence[service])
            unexpected = sorted(evidence[service] - registered)
            if missing:
                raise EvidenceCompilationError(
                    "code-owned operation lacks annotated evidence "
                    f"service={service} missing={missing}"
                )
            if unexpected:
                raise EvidenceCompilationError(
                    "annotated operation is not code-owned "
                    f"service={service} unexpected={unexpected}"
                )


class GeneratedArtifacts:
    """Own atomic output writes and drift checks for the annotation-derived artifacts."""

    def __init__(self, output: Path, english: Path, korean: Path) -> None:
        self._output = output
        self._english = english
        self._korean = korean

    def expected(self, compiled: dict[str, Any]) -> dict[Path, str]:
        return {
            self._output: json.dumps(compiled, indent=2, sort_keys=True) + "\n",
            self._english: _render(compiled, korean=False),
            self._korean: _render(compiled, korean=True),
        }

    def check(self, expected: dict[Path, str]) -> None:
        drifted = [path for path, content in expected.items() if _read(path) != content]
        if drifted:
            raise EvidenceCompilationError(
                "annotated compatibility evidence drift paths="
                + ",".join(str(path) for path in drifted)
                + "; fix_hint=run-make-compatibility-evidence-generate"
            )

    def write(self, expected: dict[Path, str]) -> None:
        for path, content in expected.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            try:
                temporary.write_text(content, encoding="utf-8")
                temporary.replace(path)
            finally:
                if temporary.exists():
                    temporary.unlink()


def _matrices(cases: Iterable[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    matrices = {
        f"{lane}_{kind}": {"include": []}
        for lane in ("required", "preview", "nightly")
        for kind in ("contract", "e2e")
    }
    for case in cases:
        key = f"{case['lane']}_{case['scenario']['kind']}"
        matrices[key]["include"].append(
            {
                "case_id": case["id"],
                "evidence_sha256": case["evidence_sha256"],
                "python_version": case["runtime"]["python_version"],
                "timeout_minutes": case["expected_duration_minutes"],
            }
        )
    return matrices


def _render(compiled: dict[str, Any], *, korean: bool) -> str:
    if korean:
        title = "# 생성된 테스트 선언 호환성 근거"
        contents_title = "## 목차"
        contents_entry = "- [공식 참고 자료](#공식-참고-자료)"
        intro = (
            "이 문서는 pytest `mystack_compatibility` annotation에서 결정적으로 생성됩니다. "
            "각 행은 test body를 실행하지 않는 collection 결과로 선택한 CI case입니다."
        )
        headings = (
            "| Case | Lane | Runtime | 고정 버전 | Scenario | 근거 hash |\n"
            "| --- | --- | --- | --- | --- | --- |"
        )
        source_heading = "## 공식 참고 자료"
        source_label = "공식 자료"
    else:
        title = "# Generated test-declared compatibility evidence"
        contents_title = "## Contents"
        contents_entry = "- [Official references](#official-references)"
        intro = (
            "This document is generated deterministically from pytest `mystack_compatibility` "
            "annotations. Each row is a CI case selected by collection without executing "
            "test bodies."
        )
        headings = (
            "| Case | Lane | Runtime | Exact versions | Scenarios | Evidence hash |\n"
            "| --- | --- | --- | --- | --- | --- |"
        )
        source_heading = "## Official references"
        source_label = "official source"
    lines = [
        title,
        "",
        "<!-- toc:start -->",
        contents_title,
        "",
        contents_entry,
        "<!-- toc:end -->",
        "",
        intro,
        "",
        headings,
    ]
    urls: set[str] = set()
    for case in compiled["cases"]:
        profile = next(iter(case["compatibility_profiles"].values()))
        versions = ", ".join(
            f"{name} {value}" for name, value in sorted(profile["versions"].items())
        )
        scenarios = ", ".join(case["scenario"]["scenario_ids"])
        lines.append(
            f"| `{case['id']}` | `{case['lane']}` | `{case['runtime_profile_id']}` | "
            f"{versions} | {scenarios} | `{case['evidence_sha256'][:16]}` |"
        )
        urls.update(profile["reference_urls"])
    lines.extend(["", source_heading, ""])
    lines.extend(f"- [{source_label}]({url})" for url in sorted(urls))
    return "\n".join(lines) + "\n"


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceCompilationError(f"cannot load JSON path={path}: {error}") from error
    return _mapping(value, str(path))


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise EvidenceCompilationError(f"cannot load YAML path={path}: {error}") from error
    return _mapping(value, str(path))


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceCompilationError(f"expected mapping path={path}")
    return value


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceCompilationError(f"expected non-empty string path={path}")
    return value


def _strings(value: object, path: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        prefix = "possibly empty " if allow_empty else ""
        raise EvidenceCompilationError(f"expected {prefix}string list path={path}")
    if any(not isinstance(item, str) or not item for item in value) or len(value) != len(
        set(value)
    ):
        raise EvidenceCompilationError(f"expected unique non-empty string list path={path}")
    return value


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _tail(value: str | bytes | None, limit: int = 4_000) -> str:
    """Bound collection diagnostics so a malformed marker never floods CI logs."""

    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = _SENSITIVE_DIAGNOSTIC_HEADER.sub(
        lambda match: f"{match.group('name')}{match.group('separator')}<redacted>", value
    )
    value = _SENSITIVE_BEARER_VALUE.sub("Bearer <redacted>", value)
    value = _SENSITIVE_DIAGNOSTIC_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", value
    )
    tail = value[-limit:]
    return tail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--collection", type=Path, help="use a pre-collected JSON document")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--english", type=Path, default=DEFAULT_ENGLISH)
    parser.add_argument("--korean", type=Path, default=DEFAULT_KOREAN)
    parser.add_argument(
        "--config",
        type=Path,
        default=_configured_config_path(),
        help="YAML configuration that supplies runtime facts and the collection timeout",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = parse_args()
    try:
        collected = (
            _load_json(args.collection)
            if args.collection
            else collect_annotations(config_path=args.config)
        )
        compiled = EvidenceCompiler(config_path=args.config).compile(collected)
        artifacts = GeneratedArtifacts(args.output, args.english, args.korean)
        expected = artifacts.expected(compiled)
        if args.write:
            artifacts.write(expected)
        else:
            artifacts.check(expected)
        return 0
    except EvidenceCompilationError as error:
        LOGGER.error("event=compatibility.annotation.failed error=%s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
