"""Create and verify immutable, cross-workflow build-artifact manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


class ArtifactError(ValueError):
    """A reusable build artifact is stale, corrupt, or from an incompatible producer."""


def should_rebuild(download_outcome: str) -> bool:
    """Only an unavailable artifact may fall back; a downloaded mismatch is rejected."""

    return download_outcome != "success"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(paths: list[Path], *, root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for input_path in paths:
        path = input_path if input_path.is_absolute() else root / input_path
        if not path.exists():
            raise ArtifactError(f"artifact input missing path={input_path}")
        candidates = (
            [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        )
        for candidate in candidates:
            result[candidate.relative_to(root).as_posix()] = _digest(candidate)
    return dict(sorted(result.items()))


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def create(arguments: argparse.Namespace) -> dict[str, object]:
    root = arguments.root.resolve()
    inputs = _files(arguments.input, root=root)
    artifacts = _files(arguments.artifact, root=root)
    return {
        "schema_version": 1,
        "source_sha": arguments.source_sha,
        "platform": arguments.platform,
        "producer": {"workflow": arguments.producer_workflow, "run_id": arguments.producer_run_id},
        "retention_days": arguments.retention_days,
        "configuration_sha256": _canonical_digest(inputs),
        "inputs": inputs,
        "files": artifacts,
    }


def verify(arguments: argparse.Namespace) -> None:
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ArtifactError("artifact manifest schema mismatch")
    if manifest.get("source_sha") != arguments.source_sha:
        raise ArtifactError("artifact source SHA mismatch; rebuild the frontend bundle")
    if manifest.get("platform") != arguments.platform:
        raise ArtifactError("artifact platform mismatch; rebuild the frontend bundle")
    root = arguments.root.resolve()
    inputs = _files(arguments.input, root=root)
    if manifest.get("configuration_sha256") != _canonical_digest(inputs):
        raise ArtifactError("artifact configuration digest mismatch; rebuild the frontend bundle")
    if manifest.get("inputs") != inputs:
        raise ArtifactError("artifact input digest mismatch; rebuild the frontend bundle")
    artifacts = _files(arguments.artifact, root=root)
    if manifest.get("files") != artifacts:
        raise ArtifactError("artifact file digest mismatch; rebuild the frontend bundle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    command = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "verify"):
        child = command.add_parser(name)
        child.add_argument("--source-sha", required=True)
        child.add_argument("--platform", required=True)
        child.add_argument("--input", type=Path, action="append", required=True)
        child.add_argument("--artifact", type=Path, action="append", required=True)
        if name == "create":
            child.add_argument("--manifest", type=Path, required=True)
            child.add_argument("--producer-workflow", required=True)
            child.add_argument("--producer-run-id", required=True)
            child.add_argument("--retention-days", type=int, required=True)
        else:
            child.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        if arguments.command == "create":
            manifest = create(arguments)
            arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
            arguments.manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "event": "reusable_build_artifact.created",
                        "manifest": str(arguments.manifest),
                    }
                )
            )
        else:
            verify(arguments)
            print(
                json.dumps(
                    {
                        "event": "reusable_build_artifact.verified",
                        "manifest": str(arguments.manifest),
                    }
                )
            )
    except (ArtifactError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"event": "reusable_build_artifact.rejected", "error": str(error)}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
