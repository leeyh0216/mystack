"""Image-only Compose policy based on the official Compose specification.

https://docs.docker.com/reference/compose-file/
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.check_ghcr_compose import (
    PUBLIC_PACKAGE_SOURCE,
    ImageComposeContractError,
    ImageComposePolicy,
    PublicImageDocumentationPolicy,
    load_compose,
)

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ghcr.yaml"


def test_committed_user_compose_is_source_free_and_explicitly_versioned() -> None:
    report = ImageComposePolicy().validate(load_compose(COMPOSE))

    assert report["services"] == ["emr", "glue", "localstack", "proxy"]
    assert report["build_keys"] == 0
    assert all("ghcr.io/leeyh0216/mystack-" in image for image in report["images"].values())
    assert all("MYSTACK_IMAGE_TAG:?" in image for image in report["images"].values())


def test_policy_rejects_a_nested_build_context() -> None:
    document = load_compose(COMPOSE)
    document["services"]["proxy"]["build"] = {"context": "."}

    with pytest.raises(ImageComposeContractError, match="build keys"):
        ImageComposePolicy().validate(document)


@pytest.mark.parametrize("tag", ("latest", "dev"))
def test_policy_rejects_mutable_or_development_tags(tag: str) -> None:
    document = copy.deepcopy(load_compose(COMPOSE))
    document["services"]["proxy"]["image"] = f"ghcr.io/leeyh0216/mystack-proxy:{tag}"

    with pytest.raises(ImageComposeContractError, match="explicit GHCR tag|forbidden"):
        ImageComposePolicy().validate(document)


def test_user_docs_require_anonymous_public_image_onboarding() -> None:
    documents = {
        ROOT / "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        ROOT / "README.ko.md": (ROOT / "README.ko.md").read_text(encoding="utf-8"),
        ROOT / "docs/getting-started.md": (ROOT / "docs/getting-started.md").read_text(
            encoding="utf-8"
        ),
        ROOT / "docs/getting-started.ko.md": (ROOT / "docs/getting-started.ko.md").read_text(
            encoding="utf-8"
        ),
    }

    report = PublicImageDocumentationPolicy().validate(documents)

    assert report["visibility"] == "public"
    assert report["consumer_registry_credentials"] == 0


@pytest.mark.parametrize("forbidden", ("docker login ghcr.io", "read:packages", "CR_PAT"))
def test_public_image_docs_reject_consumer_registry_credentials(forbidden: str) -> None:
    documents = {
        Path("README.md"): f"Pull anonymously. {PUBLIC_PACKAGE_SOURCE}\n{forbidden}\n",
        Path("README.ko.md"): f"익명으로 pull합니다. {PUBLIC_PACKAGE_SOURCE}\n",
    }

    with pytest.raises(ImageComposeContractError, match="onboarding policy"):
        PublicImageDocumentationPolicy().validate(documents)
