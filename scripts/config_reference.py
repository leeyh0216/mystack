"""Render the complete user configuration reference from schema and defaults."""

from __future__ import annotations

import argparse
import functools
import json
import operator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "shared/src/mystack/aws_protocol/mystack.schema.json"
CONFIG = ROOT / "config/runtime/mystack.yaml"
OUT = ROOT / "docs/configuration-reference.generated.md"


def resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[1]]
    return schema


def leaves(
    schema: dict[str, Any], value: Any, root: dict[str, Any], path: str = ""
) -> list[tuple[str, dict[str, Any], Any]]:
    schema = resolve(schema, root)
    properties = schema.get("properties")
    if properties:
        result = []
        for name, child in properties.items():
            next_path = f"{path}.{name}" if path else name
            result += leaves(
                child, value.get(name) if isinstance(value, dict) else None, root, next_path
            )
        return result
    if "additionalProperties" in schema and isinstance(value, dict):
        child = schema["additionalProperties"]
        if isinstance(child, dict):
            return functools.reduce(
                operator.iadd,
                (leaves(child, item, root, f"{path}.{name}") for name, item in value.items()),
                [],
            )
    return [(path, schema, value)]


def validation(schema: dict[str, Any]) -> str:
    keys = (
        "const",
        "enum",
        "type",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "minLength",
        "minItems",
        "pattern",
        "format",
    )
    return "; ".join(f"{key}={schema[key]!r}" for key in keys if key in schema) or "schema-defined"


def owner(path: str) -> str:
    return path.split(".", 1)[0]


def render() -> str:
    root = json.loads(SCHEMA.read_text())
    values = yaml.safe_load(CONFIG.read_text())
    rows = leaves(root, values, root)
    lines = [
        "# Generated configuration reference",
        "",
        "<!-- toc:start -->",
        "## Contents",
        "",
        "- [Complete leaf keys](#complete-leaf-keys)",
        "<!-- toc:end -->",
        "",
        "Do not edit: generated from the runtime JSON Schema and `config/runtime/mystack.yaml`.",
        "All values load once at process startup; restart the affected service after a change.",
        "",
        "## Complete leaf keys",
        "",
        "| Path | Type / validation | Default or example | Owner | Effect / reload |",
        "| --- | --- | --- | --- | --- |",
    ]
    for path, schema, value in rows:
        rule = validation(resolve(schema, root)).replace("|", "&#124;")
        rendered_value = json.dumps(value, ensure_ascii=False)
        lines.append(
            f"| `{path}` | {rule} | `{rendered_value}` | `{owner(path)}` | "
            "Runtime configuration; restart required |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not OUT.is_file() or OUT.read_text() != text:
            raise SystemExit("configuration reference drift; run scripts/config_reference.py")
    else:
        OUT.write_text(text)


if __name__ == "__main__":
    main()
