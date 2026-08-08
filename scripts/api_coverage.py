"""Generate and verify the complete EMR/Glue operation classification.

Official inventory source:
https://github.com/boto/botocore/tree/develop/botocore/data

The committed baseline is intentionally exhaustive. ``--check`` never assigns a default status
to a newly discovered operation: upstream additions remain unclassified and fail CI until a
maintainer reviews and writes their explicit status.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.model_manifest import SERVICES, create_manifest
except ModuleNotFoundError:  # Direct ``python scripts/api_coverage.py`` execution.
    from model_manifest import SERVICES, create_manifest

ALLOWED_STATUSES = frozenset({"COMPATIBLE", "PARTIAL", "PROTOCOL_ONLY", "NOT_PLANNED"})
IMPLEMENTED = {
    "emr": frozenset(
        {
            "AddJobFlowSteps",
            "AddTags",
            "CancelSteps",
            "DescribeCluster",
            "DescribeStep",
            "ListBootstrapActions",
            "ListClusters",
            "ListSteps",
            "RemoveTags",
            "RunJobFlow",
            "SetTerminationProtection",
            "SetVisibleToAllUsers",
            "TerminateJobFlows",
        }
    ),
    "glue": frozenset(
        {
            "BatchCreatePartition",
            "BatchDeletePartition",
            "BatchGetPartition",
            "BatchUpdatePartition",
            "CreateDatabase",
            "CreatePartition",
            "CreateTable",
            "DeleteDatabase",
            "DeletePartition",
            "DeleteTable",
            "GetCatalogImportStatus",
            "GetDatabase",
            "GetDatabases",
            "GetPartition",
            "GetPartitions",
            "GetTable",
            "GetTables",
            "GetTableVersion",
            "GetTableVersions",
            "UpdateDatabase",
            "UpdatePartition",
            "UpdateTable",
        }
    ),
}


def initial_status(service: str, operation: str) -> str:
    if operation in IMPLEMENTED[service]:
        return "COMPATIBLE"
    if service == "glue" and any(token in operation for token in ("Job", "JobRun", "Crawler")):
        return "NOT_PLANNED"
    return "PROTOCOL_ONLY"


def create_baseline(manifest: dict[str, Any]) -> dict[str, Any]:
    services: dict[str, Any] = {}
    for service in SERVICES:
        model = manifest["services"][service]
        services[service] = {
            "model_fingerprint": model["model_fingerprint"],
            "operations": {
                name: {
                    "fingerprint": fingerprint,
                    "status": initial_status(service, name),
                }
                for name, fingerprint in model["operation_fingerprints"].items()
            },
        }
    return {
        "schema_version": 1,
        "source": "official botocore service-2 models",
        "source_url": "https://github.com/boto/botocore/tree/develop/botocore/data",
        "botocore_version": manifest["botocore_version"],
        "status_definitions": {
            "COMPATIBLE": (
                "Wire shape and documented semantics have contracts and public Proxy E2E."
            ),
            "PARTIAL": "The operation works but documented semantic branches remain incomplete.",
            "PROTOCOL_ONLY": "The pinned wire model is known; semantic implementation is pending.",
            "NOT_PLANNED": "The operation is explicitly outside Mystack scope.",
        },
        "services": services,
    }


def compare(baseline: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "expected_botocore_version": baseline.get("botocore_version"),
        "actual_botocore_version": manifest["botocore_version"],
        "services": {},
        "fix_hints": [
            "Unclassified additions: review the official API, then add an explicit entry to "
            "contracts/api-coverage.json.",
            "Changed operations: update the owning inbound adapter, modeled-error contracts, "
            "and public Proxy E2E before refreshing its fingerprint.",
            "Removed operations: document the compatibility decision before deleting the "
            "classification entry.",
            "Status changes: regenerate both api-coverage.generated.md files and update support "
            "scope when behavior changes.",
        ],
    }
    for service in SERVICES:
        expected = baseline.get("services", {}).get(service, {}).get("operations", {})
        actual = manifest["services"][service]["operation_fingerprints"]
        expected_names = set(expected)
        actual_names = set(actual)
        invalid_statuses = {
            name: value.get("status")
            for name, value in expected.items()
            if not isinstance(value, dict) or value.get("status") not in ALLOWED_STATUSES
        }
        changed = sorted(
            name
            for name in expected_names & actual_names
            if expected[name].get("fingerprint") != actual[name]
        )
        implemented_misclassified = sorted(
            name
            for name in IMPLEMENTED[service]
            if expected.get(name, {}).get("status") not in {"COMPATIBLE", "PARTIAL"}
        )
        report["services"][service] = {
            "operations_total": len(actual),
            "status_counts": dict(
                sorted(Counter(value.get("status") for value in expected.values()).items())
            ),
            "operations_added_unclassified": sorted(actual_names - expected_names),
            "operations_removed": sorted(expected_names - actual_names),
            "operations_changed": changed,
            "invalid_statuses": invalid_statuses,
            "implemented_misclassified": implemented_misclassified,
        }
    return report


def has_drift(report: dict[str, Any]) -> bool:
    drift_keys = (
        "operations_added_unclassified",
        "operations_removed",
        "operations_changed",
        "invalid_statuses",
        "implemented_misclassified",
    )
    return any(service[key] for service in report["services"].values() for key in drift_keys)


def render_matrix(baseline: dict[str, Any], *, korean: bool) -> str:
    if korean:
        title = "# 생성된 API 호환성 Matrix"
        intro = (
            "이 파일은 `contracts/api-coverage.json`에서 생성됩니다. 직접 수정하지 마세요. "
            "공식 inventory는 [botocore service model]"
            "(https://github.com/boto/botocore/tree/develop/botocore/data)입니다."
        )
        headings = "| 서비스 | Operation | 상태 | 설명 |\n| --- | --- | --- | --- |"
        descriptions = {
            "COMPATIBLE": "boto3 계약 및 public Proxy E2E 구현",
            "PARTIAL": "일부 문서화된 의미 분기 미구현",
            "PROTOCOL_ONLY": "고정 wire model만 추적, 의미 구현 대기",
            "NOT_PLANNED": "Glue Job/JobRun/Crawler 범위 제외",
        }
        summary_heading = "## 요약"
    else:
        title = "# Generated API compatibility matrix"
        intro = (
            "This file is generated from `contracts/api-coverage.json`; do not edit it directly. "
            "The official inventory is the [botocore service model]"
            "(https://github.com/boto/botocore/tree/develop/botocore/data)."
        )
        headings = "| Service | Operation | Status | Meaning |\n| --- | --- | --- | --- |"
        descriptions = {
            "COMPATIBLE": "Implemented with boto3 contracts and public Proxy E2E",
            "PARTIAL": "Some documented semantic branches remain",
            "PROTOCOL_ONLY": "Pinned wire model tracked; semantics pending",
            "NOT_PLANNED": "Glue Job/JobRun/Crawler family excluded",
        }
        summary_heading = "## Summary"

    lines = [
        title,
        "",
        intro,
        "",
        f"botocore: `{baseline['botocore_version']}`",
        "",
        summary_heading,
        "",
        "| Service | COMPATIBLE | PARTIAL | PROTOCOL_ONLY | NOT_PLANNED | Total |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for service in SERVICES:
        operations = baseline["services"][service]["operations"]
        counts = Counter(value["status"] for value in operations.values())
        lines.append(
            f"| {service.upper()} | {counts['COMPATIBLE']} | {counts['PARTIAL']} | "
            f"{counts['PROTOCOL_ONLY']} | {counts['NOT_PLANNED']} | {len(operations)} |"
        )
    lines.extend(["", headings])
    for service in SERVICES:
        for operation, value in baseline["services"][service]["operations"].items():
            status = value["status"]
            lines.append(
                f"| {service.upper()} | `{operation}` | `{status}` | {descriptions[status]} |"
            )
    return "\n".join(lines) + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--bootstrap", type=Path)
    mode.add_argument("--check", type=Path)
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--korean", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("api-coverage-drift-report.json"))
    args = parser.parse_args()

    manifest = create_manifest()
    if args.bootstrap:
        baseline = create_baseline(manifest)
        write_text(args.bootstrap, json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    else:
        baseline = json.loads(args.check.read_text(encoding="utf-8"))

    english = render_matrix(baseline, korean=False)
    korean = render_matrix(baseline, korean=True)
    if args.bootstrap:
        write_text(args.english, english)
        write_text(args.korean, korean)
        return 0

    report = compare(baseline, manifest)
    generated_drift = []
    for path, expected in ((args.english, english), (args.korean, korean)):
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            generated_drift.append(str(path))
    report["generated_documents_out_of_date"] = generated_drift
    write_text(args.report, json.dumps(report, indent=2, sort_keys=True) + "\n")
    drifted = has_drift(report) or bool(generated_drift)
    print(
        json.dumps(
            {
                "event": "compatibility.api_coverage.drift"
                if drifted
                else "compatibility.api_coverage.clean",
                "report_path": str(args.report),
                "services": report["services"],
                "generated_documents_out_of_date": generated_drift,
            },
            sort_keys=True,
        )
    )
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
