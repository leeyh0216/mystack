"""Versioned YAML configuration with Docker-friendly nested environment overrides.

Docker configuration references:
- https://docs.docker.com/reference/compose-file/configs/
- https://docs.docker.com/compose/how-tos/use-secrets/

Environment overrides use MYSTACK__SECTION__KEY. Values are parsed as YAML scalars or
collections, so booleans and numeric timeouts retain their types.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .observability import log_event

_LOGGER = logging.getLogger(__name__)
_NESTED_PREFIX = "MYSTACK__"
_SENSITIVE_SEGMENTS = {"authorization", "credential", "key", "password", "secret", "token"}


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedConfiguration:
    document: dict[str, Any]
    source: str
    fingerprint: str
    override_paths: tuple[str, ...]


def load_configuration(path: str | Path | None = None) -> LoadedConfiguration:
    configured_path = path or os.getenv("MYSTACK_CONFIG_FILE") or "config/mystack.yaml"
    source = Path(configured_path).expanduser().resolve()
    if not source.is_file():
        raise ConfigurationError(
            f"Mystack configuration does not exist: {source}. "
            "Set MYSTACK_CONFIG_FILE or pass --config."
        )
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {source}")
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise ConfigurationError(
            f"Unsupported configuration schema_version={schema_version!r}; expected 1"
        )

    override_paths: list[str] = []
    for variable, value in sorted(os.environ.items()):
        if not variable.startswith(_NESTED_PREFIX):
            continue
        parts = tuple(part.lower() for part in variable.removeprefix(_NESTED_PREFIX).split("__"))
        if not all(parts):
            raise ConfigurationError(f"Invalid nested override name: {variable}")
        _set_nested(raw, parts, yaml.safe_load(value))
        override_paths.append(".".join(parts))

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    safe_override_paths = tuple(_redact_path(path) for path in override_paths)
    log_event(
        _LOGGER,
        logging.INFO,
        "configuration.loaded",
        source=str(source),
        schema_version=schema_version,
        fingerprint=fingerprint,
        override_paths=safe_override_paths,
        fix_hint=(
            "Edit the mounted YAML file for durable changes; use MYSTACK__SECTION__KEY "
            "for deployment-specific overrides."
        ),
    )
    return LoadedConfiguration(raw, str(source), fingerprint, safe_override_paths)


def require_mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section {key!r} must be a mapping")
    return value


def _set_nested(document: dict[str, Any], parts: tuple[str, ...], value: Any) -> None:
    cursor = document
    for part in parts[:-1]:
        current = cursor.get(part)
        if current is None:
            current = {}
            cursor[part] = current
        if not isinstance(current, dict):
            path = ".".join(parts)
            raise ConfigurationError(f"Cannot apply override {path}: parent is not a mapping")
        cursor = current
    cursor[parts[-1]] = value


def _redact_path(path: str) -> str:
    segments = path.lower().split(".")
    if any(sensitive in segment for segment in segments for sensitive in _SENSITIVE_SEGMENTS):
        return "<sensitive-path>"
    return path
