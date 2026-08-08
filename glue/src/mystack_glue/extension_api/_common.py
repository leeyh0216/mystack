"""Shared public values for the versioned Glue extension SPIs.

Entry-point specification:
https://packaging.python.org/en/latest/specifications/entry-points/
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlueExtensionIdentity:
    extension_id: str
    entry_point: str
    operations: tuple[str, ...]
    api_version: int
