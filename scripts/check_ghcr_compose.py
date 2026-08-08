"""Enforce the source-free, anonymously pullable GHCR user contract.

Official references:
- Compose interpolation: https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/
- GHCR package permissions: https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

import yaml

PUBLIC_PACKAGE_SOURCE = (
    "https://docs.github.com/en/packages/learn-github-packages/"
    "about-permissions-for-github-packages"
)
DEFAULT_USER_DOCS = (
    Path("README.md"),
    Path("README.ko.md"),
    Path("docs/getting-started.md"),
    Path("docs/getting-started.ko.md"),
)


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


class PublicImageDocumentationPolicy:
    """Keep public-image onboarding free of consumer registry credentials."""

    FORBIDDEN: ClassVar[tuple[str, ...]] = (
        "docker login ghcr.io",
        "read:packages",
        "CR_PAT",
        "private GHCR",
        "private published images",
    )

    def validate(self, documents: dict[Path, str]) -> dict[str, Any]:
        ImageComposePolicy._emit(
            "ghcr_public_docs.validate.before",
            documents=[str(path) for path in documents],
        )
        violations: list[str] = []
        for path, content in documents.items():
            for forbidden in self.FORBIDDEN:
                if forbidden.casefold() in content.casefold():
                    violations.append(f"{path}:{forbidden}")
            required_phrase = "익명" if path.name.endswith(".ko.md") else "anonym"
            if required_phrase.casefold() not in content.casefold():
                violations.append(f"{path}:missing-{required_phrase}")
            if PUBLIC_PACKAGE_SOURCE not in content:
                violations.append(f"{path}:missing-official-public-package-source")
        if violations:
            ImageComposePolicy._emit(
                "ghcr_public_docs.validate.failed",
                violations=violations,
                fix_hint="describe-anonymous-public-pulls-without-consumer-registry-credentials",
            )
            raise ImageComposeContractError(
                "public image onboarding policy violations: " + ", ".join(violations)
            )
        ImageComposePolicy._emit(
            "ghcr_public_docs.validate.after",
            documents=[str(path) for path in documents],
            consumer_registry_credentials=0,
        )
        return {
            "documents": [str(path) for path in documents],
            "consumer_registry_credentials": 0,
            "visibility": "public",
        }


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


def load_documents(paths: tuple[Path, ...]) -> dict[Path, str]:
    documents: dict[Path, str] = {}
    for path in paths:
        ImageComposePolicy._emit("ghcr_public_docs.read.before", path=str(path))
        documents[path] = path.read_text(encoding="utf-8")
        ImageComposePolicy._emit("ghcr_public_docs.read.after", path=str(path))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, default=Path("compose.ghcr.yaml"))
    parser.add_argument(
        "--user-doc",
        action="append",
        type=Path,
        dest="user_docs",
        help="User-facing document to validate; defaults to both README and usage-guide languages",
    )
    args = parser.parse_args()
    try:
        compose_report = ImageComposePolicy().validate(load_compose(args.compose))
        public_docs_report = PublicImageDocumentationPolicy().validate(
            load_documents(tuple(args.user_docs or DEFAULT_USER_DOCS))
        )
        report = {"compose": compose_report, "public_image_docs": public_docs_report}
    except (OSError, yaml.YAMLError, ImageComposeContractError) as error:
        print(
            json.dumps(
                {
                    "event": "ghcr_compose.validate.failed",
                    "error": str(error),
                    "fix_hint": (
                        "remove-build-context-pin-explicit-published-images-and-keep-"
                        "public-onboarding-anonymous"
                    ),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from error
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
