"""Enforce the source-free GHCR Compose contract.

Official references:
- Compose interpolation: https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/
- GHCR authentication: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

import yaml


class ImageComposeContractError(RuntimeError):
    """The user deployment would need source files or a mutable image identity."""


class ImageComposePolicy:
    """Validate only image-delivery concerns, independent of Docker process execution."""

    REQUIRED_SERVICES = frozenset({"proxy", "emr", "glue", "localstack"})
    PACKAGES: ClassVar[dict[str, str]] = {
        "proxy": "mystack-proxy",
        "emr": "mystack-emr",
        "glue": "mystack-glue",
    }

    def validate(self, document: dict[str, Any]) -> dict[str, Any]:
        self._emit("ghcr_compose.validate.before")
        services = document.get("services")
        if not isinstance(services, dict) or set(services) != self.REQUIRED_SERVICES:
            raise ImageComposeContractError(
                f"services must be exactly {sorted(self.REQUIRED_SERVICES)}"
            )
        build_paths = self._find_key(document, "build")
        if build_paths:
            raise ImageComposeContractError(
                f"image-only Compose contains build keys: {sorted(build_paths)}"
            )
        images: dict[str, str] = {}
        for service, package in self.PACKAGES.items():
            image = services[service].get("image")
            if not isinstance(image, str):
                raise ImageComposeContractError(f"missing image reference: services.{service}")
            expected = f"ghcr.io/leeyh0216/{package}:"
            if expected not in image or "MYSTACK_IMAGE_TAG:?" not in image:
                raise ImageComposeContractError(
                    f"Mystack image must require an explicit GHCR tag: services.{service}.image"
                )
            if ":latest" in image or ":dev" in image:
                raise ImageComposeContractError(
                    f"mutable/development tag is forbidden: services.{service}.image"
                )
            images[service] = image
        localstack = services["localstack"].get("image", "")
        if not re.search(r"@sha256:[0-9a-f]{64}", localstack):
            raise ImageComposeContractError("LocalStack default image must be digest pinned")
        self._emit("ghcr_compose.validate.after", services=sorted(services), build_keys=0)
        return {"services": sorted(services), "images": images, "build_keys": 0}

    @classmethod
    def _find_key(cls, value: Any, target: str, path: str = "root") -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == target:
                    found.append(child_path)
                found.extend(cls._find_key(child, target, child_path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                found.extend(cls._find_key(child, target, f"{path}[{index}]"))
        return found

    @staticmethod
    def _emit(event: str, **fields: Any) -> None:
        print(json.dumps({"event": event, **fields}, sort_keys=True), file=sys.stderr)


def load_compose(path: Path) -> dict[str, Any]:
    print(
        json.dumps({"event": "ghcr_compose.read.before", "path": str(path)}, sort_keys=True),
        file=sys.stderr,
    )
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ImageComposeContractError("Compose root must be a mapping")
    print(
        json.dumps({"event": "ghcr_compose.read.after", "path": str(path)}, sort_keys=True),
        file=sys.stderr,
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, default=Path("compose.ghcr.yaml"))
    args = parser.parse_args()
    try:
        report = ImageComposePolicy().validate(load_compose(args.compose))
    except (OSError, yaml.YAMLError, ImageComposeContractError) as error:
        print(
            json.dumps(
                {
                    "event": "ghcr_compose.validate.failed",
                    "error": str(error),
                    "fix_hint": "remove-build-context-and-pin-explicit-published-images",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from error
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
