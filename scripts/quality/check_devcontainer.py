"""Validate the reproducible Mystack Dev Container contract.

Official references:
- https://containers.dev/implementors/json_reference/
- https://github.com/devcontainers/cli#pre-building
- https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker
- https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
CONFIG_PATH = ROOT / ".devcontainer" / "devcontainer.json"
DOCKERFILE_PATH = ROOT / ".devcontainer" / "Dockerfile"
IMAGES_PATH = ROOT / ".devcontainer" / "images.json"
LOCK_PATH = ROOT / ".devcontainer" / "devcontainer-lock.json"
EXACT_FEATURE = re.compile(r"^ghcr\.io/devcontainers/features/[a-z0-9-]+:\d+\.\d+\.\d+$")
DIGEST_REFERENCE = re.compile(r"@sha256:[0-9a-f]{64}(?:\s|$)")
RESOLVED_FEATURE = re.compile(
    r"^ghcr\.io/devcontainers/features/[a-z0-9-]+@(?P<digest>sha256:[0-9a-f]{64})$"
)


class DevContainerContract:
    """Collect every configuration violation before failing the contributor check."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.violations: list[str] = []
        self.images = self._load_json(IMAGES_PATH, "image lock")
        self.feature_lock = self._load_json(LOCK_PATH, "Dev Container feature lock")

    def validate(self) -> None:
        document = self._load_json(CONFIG_PATH, "Dev Container configuration")
        self._validate_schema(document)
        self._validate_features(document)
        self._validate_feature_lock(document)
        self._validate_workspace(document)
        self._validate_lifecycle(document)
        self._validate_dockerfile()
        if self.violations:
            raise SystemExit("Dev Container contract violations:\n" + "\n".join(self.violations))
        print("devcontainer.contract.clean")

    def verify_images(self) -> None:
        for name in ("base", "uv"):
            locked = self.images.get(name)
            if not isinstance(locked, dict):
                raise SystemExit(f"Dev Container image lock is missing {name!r}")
            reference = str(locked.get("reference", ""))
            expected = str(locked.get("digest", ""))
            completed = subprocess.run(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    reference,
                    "--format",
                    "{{json .Manifest}}",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.returncode != 0:
                raise SystemExit(f"Cannot inspect Dev Container image {reference!r}")
            manifest = json.loads(completed.stdout)
            actual = manifest.get("digest")
            if actual != expected:
                raise SystemExit(
                    f"Dev Container image drift for {reference}: expected {expected}, got {actual}"
                )
        print("devcontainer.images.clean")

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"Cannot read {path}: {error}") from error
        if not isinstance(document, dict):
            raise SystemExit(f"{label} must be a JSON object")
        return document

    def _validate_schema(self, document: dict[str, Any]) -> None:
        schema = document.get("$schema")
        if not isinstance(schema, str) or "githubusercontent.com/devcontainers/spec/" not in schema:
            self.violations.append(
                "$schema must reference the official Dev Container specification"
            )

    def _validate_features(self, document: dict[str, Any]) -> None:
        features = document.get("features")
        if not isinstance(features, dict) or not features:
            self.violations.append("features must be a non-empty object")
            return
        for reference, options in features.items():
            if not EXACT_FEATURE.fullmatch(reference):
                self.violations.append(f"feature must use an exact version: {reference}")
            serialized = json.dumps(options, sort_keys=True)
            if '"latest"' in serialized:
                self.violations.append(f"feature options cannot use latest: {reference}")

    def _validate_feature_lock(self, document: dict[str, Any]) -> None:
        configured = document.get("features", {})
        locked = self.feature_lock.get("features")
        if not isinstance(configured, dict) or not isinstance(locked, dict):
            self.violations.append("Dev Container feature lock must contain a features object")
            return
        if set(configured) != set(locked):
            self.violations.append(
                "Dev Container feature lock keys must exactly match configured features"
            )
            return
        for reference, lock in locked.items():
            if not isinstance(lock, dict):
                self.violations.append(f"feature lock must be an object: {reference}")
                continue
            expected_version = reference.rsplit(":", maxsplit=1)[-1]
            if lock.get("version") != expected_version:
                self.violations.append(f"feature lock version does not match: {reference}")
            resolved = str(lock.get("resolved", ""))
            match = RESOLVED_FEATURE.fullmatch(resolved)
            if match is None:
                self.violations.append(f"feature lock resolution is not digest-pinned: {reference}")
                continue
            if lock.get("integrity") != match.group("digest"):
                self.violations.append(f"feature lock integrity does not match: {reference}")

    def _validate_workspace(self, document: dict[str, Any]) -> None:
        if document.get("workspaceFolder") != "${localWorkspaceFolder}":
            self.violations.append("workspaceFolder must preserve the host absolute path")
        workspace_mount = str(document.get("workspaceMount", ""))
        if "source=${localWorkspaceFolder},target=${localWorkspaceFolder}" not in workspace_mount:
            self.violations.append("workspaceMount must preserve host/container path identity")
        endpoint = document.get("remoteEnv", {}).get("AWS_ENDPOINT_URL")
        if endpoint != "http://host.docker.internal:4566":
            self.violations.append(
                "AWS_ENDPOINT_URL must use the host gateway from the Dev Container"
            )

    def _validate_lifecycle(self, document: dict[str, Any]) -> None:
        command = document.get("postCreateCommand")
        expected = "bash scripts/development/devcontainer-setup.sh"
        if command != expected:
            self.violations.append(f"postCreateCommand must be {expected!r}")
        script = self.root / "scripts" / "development" / "devcontainer-setup.sh"
        if not script.is_file():
            self.violations.append("scripts/development/devcontainer-setup.sh is missing")

    def _validate_dockerfile(self) -> None:
        text = DOCKERFILE_PATH.read_text(encoding="utf-8")
        base = self.images.get("base", {})
        uv = self.images.get("uv", {})
        base_line = f"ARG DEVCONTAINER_BASE={base.get('reference', '')}"
        uv_repository = str(uv.get("reference", "")).split(":", maxsplit=1)[0]
        uv_reference = f"{uv_repository}@{uv.get('digest', '')}"
        if base_line not in text:
            self.violations.append("Dockerfile base reference does not match images.json")
        copy_lines = [line for line in text.splitlines() if line.startswith("COPY --from=")]
        if len(copy_lines) != 1 or uv_reference not in copy_lines[0]:
            self.violations.append("Dockerfile uv reference does not match images.json")
        elif not DIGEST_REFERENCE.search(copy_lines[0]):
            self.violations.append("Dockerfile uv reference must include a sha256 digest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-images",
        action="store_true",
        help="compare locked image digests with their current registry manifests",
    )
    arguments = parser.parse_args()
    contract = DevContainerContract()
    contract.validate()
    if arguments.verify_images:
        contract.verify_images()


if __name__ == "__main__":
    main()
