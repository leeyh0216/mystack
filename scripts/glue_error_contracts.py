#!/usr/bin/env python3
"""Validate Glue error decisions and render deterministic bilingual evidence.

Official model and exception sources:
- https://github.com/boto/botocore/tree/develop/botocore/data/glue
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import botocore.session
import yaml
from mystack.glue.adapters.inbound.aws_operations import IMPLEMENTED_GLUE_OPERATIONS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "contracts/glue-error-conditions.yaml"
DEFAULT_ENGLISH = ROOT / "docs/compatibility/glue-errors.generated.md"
DEFAULT_KOREAN = ROOT / "docs/compatibility/glue-errors.ko.generated.md"
FORBIDDEN_CODES = {
    "AccessDeniedException",
    "UnrecognizedClientException",
    "InvalidSignatureException",
}
CONDITION_KEYS = {
    "phase",
    "category",
    "error_code",
    "http_status",
    "message_template",
    "mutation_guarantee",
    "response_mode",
    "model_scope",
    "source",
}
MUTATION_GUARANTEES = {
    "handler_not_called",
    "candidate_not_committed",
    "candidate_not_published",
    "ordered_partial_success",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--english", type=Path, default=DEFAULT_ENGLISH)
    parser.add_argument("--korean", type=Path, default=DEFAULT_KOREAN)
    args = parser.parse_args()

    document = _load(args.catalog)
    _validate(document)
    outputs = {
        args.english: _render(document, korean=False),
        args.korean: _render(document, korean=True),
    }
    if args.write:
        for path, content in outputs.items():
            path.write_text(content, encoding="utf-8")
        return
    drift = [
        str(path)
        for path, content in outputs.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if drift:
        raise SystemExit(
            "Glue error contract generated output drift: "
            + ", ".join(drift)
            + "; run make glue-errors-generate"
        )


def _load(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Glue error catalog root must be a mapping")
    if set(raw) != {
        "schema_version",
        "official_sources",
        "precedence",
        "conditions",
        "operations",
    }:
        raise ValueError("Glue error catalog has unknown or missing top-level keys")
    if raw["schema_version"] != 1:
        raise ValueError("Glue error catalog schema_version must be 1")
    return raw


def _validate(document: dict[str, Any]) -> None:
    sources = _mapping(document["official_sources"], "official_sources")
    for source_id, url in sources.items():
        if not str(source_id) or not str(url).startswith("https://"):
            raise ValueError(f"Invalid official source {source_id!r}")

    precedence = document["precedence"]
    if not isinstance(precedence, list) or len(precedence) != len(set(map(str, precedence))):
        raise ValueError("precedence must be a unique list")
    phase_index = {str(value): index for index, value in enumerate(precedence)}
    required_phases = {
        "protocol_shape",
        "required_fields",
        "value_constraints",
        "fault_injection",
        "parent_existence",
        "duplicate_conflict",
        "version_concurrency",
        "mutation",
        "persistence_side_effect",
    }
    if set(phase_index) != required_phases:
        raise ValueError("precedence does not define the complete deterministic pipeline")

    conditions = _mapping(document["conditions"], "conditions")
    for condition_id, raw in conditions.items():
        condition = _mapping(raw, f"conditions.{condition_id}")
        if set(condition) != CONDITION_KEYS:
            raise ValueError(f"Condition {condition_id} has unknown or missing keys")
        if condition["phase"] not in phase_index:
            raise ValueError(f"Condition {condition_id} has an unknown phase")
        if condition["source"] not in sources:
            raise ValueError(f"Condition {condition_id} has an unknown source")
        if condition["error_code"] in FORBIDDEN_CODES:
            raise ValueError(f"Authorization error is forbidden: {condition_id}")
        if condition["mutation_guarantee"] not in MUTATION_GUARANTEES:
            raise ValueError(f"Condition {condition_id} has an invalid mutation guarantee")
        if condition["response_mode"] not in {"service_error", "batch_item"}:
            raise ValueError(f"Condition {condition_id} has an invalid response mode")
        if condition["model_scope"] not in {"operation", "global_exception"}:
            raise ValueError(f"Condition {condition_id} has an invalid model scope")
        if not isinstance(condition["http_status"], int):
            raise ValueError(f"Condition {condition_id} must have an integer HTTP status")
        if not str(condition["message_template"]):
            raise ValueError(f"Condition {condition_id} must have a message template")

    operations = _mapping(document["operations"], "operations")
    if set(operations) != set(IMPLEMENTED_GLUE_OPERATIONS):
        missing = sorted(set(IMPLEMENTED_GLUE_OPERATIONS) - set(operations))
        extra = sorted(set(operations) - set(IMPLEMENTED_GLUE_OPERATIONS))
        raise ValueError(f"Glue operation coverage drift; missing={missing}, extra={extra}")

    service = botocore.session.get_session().get_service_model("glue")
    global_errors = {
        name for name in service.shape_names if service.shape_for(name).metadata.get("exception")
    }
    for operation, raw_condition_ids in operations.items():
        if not isinstance(raw_condition_ids, list) or not raw_condition_ids:
            raise ValueError(f"Operation {operation} must reference conditions")
        condition_ids = list(map(str, raw_condition_ids))
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError(f"Operation {operation} repeats a condition")
        for required in (
            "protocol.input_shape",
            "fault.operation_timeout",
            "fault.internal_service",
            "adapter.mapping_failure",
        ):
            if required not in condition_ids:
                raise ValueError(f"Operation {operation} is missing {required}")
        ranks = [
            phase_index[str(_mapping(conditions[value], value)["phase"])] for value in condition_ids
        ]
        if ranks != sorted(ranks):
            raise ValueError(f"Operation {operation} conditions violate precedence")
        modeled_errors = {shape.name for shape in service.operation_model(operation).error_shapes}
        for condition_id in condition_ids:
            condition = _mapping(conditions.get(condition_id), condition_id)
            code = str(condition["error_code"])
            if condition["model_scope"] == "operation" and code not in modeled_errors:
                raise ValueError(
                    f"{operation}/{condition_id} uses unmodeled operation error {code}"
                )
            if condition["model_scope"] == "global_exception" and code not in global_errors:
                raise ValueError(f"{operation}/{condition_id} uses unknown global error {code}")


def _render(document: dict[str, Any], *, korean: bool) -> str:
    conditions = _mapping(document["conditions"], "conditions")
    operations = _mapping(document["operations"], "operations")
    if korean:
        title = "Glue 오류 계약 (생성됨)"
        intro = (
            "이 문서는 `contracts/glue-error-conditions.yaml`에서 결정적으로 생성됩니다. "
            "직접 수정하지 마세요."
        )
        headers = ("Operation", "결정 순서")
        source_title = "공식 출처"
        lang = "ko"
        counterpart = "glue-errors.generated.md"
        counterpart_label = "English"
    else:
        title = "Glue error contracts (generated)"
        intro = (
            "This document is generated deterministically from "
            "`contracts/glue-error-conditions.yaml`; do not edit it directly."
        )
        headers = ("Operation", "Decision order")
        source_title = "Official sources"
        lang = "en"
        counterpart = "glue-errors.ko.generated.md"
        counterpart_label = "한국어"
    lines = [
        "<!-- doc-id: compatibility/glue-errors-generated -->",
        f"<!-- lang: {lang} -->",
        "",
        f"[{counterpart_label}]({counterpart})",
        "",
        f"# {title}",
        "",
        intro,
        "",
        "<!-- section: matrix -->",
        f"## {headers[1]}",
        "",
        f"| {headers[0]} | {headers[1]} |",
        "| --- | --- |",
    ]
    for operation in sorted(operations):
        decisions = []
        for condition_id in operations[operation]:
            condition = _mapping(conditions[condition_id], condition_id)
            decisions.append(
                f"`{condition_id}` → `{condition['error_code']}`/{condition['http_status']}"
            )
        lines.append(f"| `{operation}` | {'<br>'.join(decisions)} |")
    lines.extend(
        [
            "",
            "<!-- section: sources -->",
            f"## {source_title}",
            "",
        ]
    )
    for source_id, url in _mapping(document["official_sources"], "official_sources").items():
        lines.append(f"- [{source_id}]({url})")
    lines.append("")
    return "\n".join(lines)


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a mapping")
    return value


if __name__ == "__main__":
    main()
