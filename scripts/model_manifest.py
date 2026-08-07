"""Generate and compare botocore EMR/Glue service-model contracts.

The source data is the official botocore service model repository:
https://github.com/boto/botocore/tree/develop/botocore/data

Usage:
    python scripts/model_manifest.py --write contracts/service-model-manifest.json
    python scripts/model_manifest.py --check contracts/service-model-manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import botocore
import botocore.session

SERVICES = ("emr", "glue")


def canonical_hash(document: Any) -> str:
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def operation_contract(
    operation: dict[str, Any],
    shapes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    referenced: dict[str, dict[str, Any]] = {}
    queue = list(_shape_references(operation))
    while queue:
        shape_name = queue.pop()
        if shape_name in referenced or shape_name not in shapes:
            continue
        shape = shapes[shape_name]
        referenced[shape_name] = shape
        queue.extend(_shape_references(shape))
    return {"operation": operation, "shapes": referenced}


def _shape_references(document: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "shape" and isinstance(value, str):
                found.add(value)
            else:
                found.update(_shape_references(value))
    elif isinstance(document, list):
        for value in document:
            found.update(_shape_references(value))
    return found


def create_manifest() -> dict[str, Any]:
    loader = botocore.session.get_session().get_component("data_loader")
    services: dict[str, Any] = {}
    for service_name in SERVICES:
        model = loader.load_service_model(service_name, "service-2")
        shapes = model["shapes"]
        operation_fingerprints = {
            operation_name: canonical_hash(operation_contract(operation, shapes))
            for operation_name, operation in sorted(model["operations"].items())
        }
        services[service_name] = {
            "metadata": model["metadata"],
            "model_fingerprint": canonical_hash(model),
            "operation_fingerprints": operation_fingerprints,
        }
    return {
        "schema_version": 1,
        "source": "official botocore service-2 models",
        "source_url": "https://github.com/boto/botocore/tree/develop/botocore/data",
        "botocore_version": botocore.__version__,
        "services": services,
    }


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "expected_botocore_version": expected["botocore_version"],
        "actual_botocore_version": actual["botocore_version"],
        "services": {},
        "fix_hints": [
            "Protocol metadata changes: update shared/src/mystack_aws_protocol/model.py "
            "and endpoint.py.",
            "Operation changes: update the owning EMR/Glue inbound mapper and semantic "
            "contract tests.",
            "Any operation change: update docs/compatibility API coverage in both languages.",
            "Spark, Hive or Iceberg changes: update the versioned runtime profile and "
            "Docker E2E matrix.",
        ],
    }
    for service_name in SERVICES:
        old_service = expected["services"].get(service_name, {})
        new_service = actual["services"].get(service_name, {})
        old_operations = old_service.get("operation_fingerprints", {})
        new_operations = new_service.get("operation_fingerprints", {})
        changed = sorted(
            operation
            for operation in old_operations.keys() & new_operations.keys()
            if old_operations[operation] != new_operations[operation]
        )
        report["services"][service_name] = {
            "metadata_changed": old_service.get("metadata") != new_service.get("metadata"),
            "model_fingerprint_before": old_service.get("model_fingerprint"),
            "model_fingerprint_after": new_service.get("model_fingerprint"),
            "operations_added": sorted(new_operations.keys() - old_operations.keys()),
            "operations_removed": sorted(old_operations.keys() - new_operations.keys()),
            "operations_changed": changed,
        }
    return report


def has_drift(report: dict[str, Any]) -> bool:
    for service in report["services"].values():
        if service["metadata_changed"]:
            return True
        if any(
            service[key] for key in ("operations_added", "operations_removed", "operations_changed")
        ):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", type=Path)
    mode.add_argument("--check", type=Path)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("model-drift-report.json"),
    )
    args = parser.parse_args()
    actual = create_manifest()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "event": "protocol.model_manifest.written",
                    "path": str(args.write),
                    "botocore_version": actual["botocore_version"],
                },
                sort_keys=True,
            )
        )
        return 0

    expected = json.loads(args.check.read_text(encoding="utf-8"))
    report = compare(expected, actual)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    drifted = has_drift(report)
    print(
        json.dumps(
            {
                "event": "protocol.model_drift.detected"
                if drifted
                else "protocol.model_drift.clean",
                "report": report,
                "report_path": str(args.report),
            },
            sort_keys=True,
        )
    )
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
