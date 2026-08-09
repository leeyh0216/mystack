"""Image-only Compose policy based on the official Compose specification.

https://docs.docker.com/reference/compose-file/
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.quality.check_ghcr_compose import (
    ImageComposeContractError,
    ImageComposePolicy,
    PublishedImageDocumentationPolicy,
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


def test_user_docs_require_the_versioned_published_image_workflow() -> None:
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

    report = PublishedImageDocumentationPolicy().validate(documents)

    assert report["versioned_compose_workflow"] is True
    assert report["consumer_registry_credentials"] == 0


@pytest.mark.parametrize("forbidden", ("docker login ghcr.io", "read:packages", "CR_PAT"))
def test_published_image_docs_reject_consumer_registry_credentials(forbidden: str) -> None:
    documents = {
        Path("README.md"): f"MYSTACK_IMAGE_TAG\ncompose.ghcr.yaml\n{forbidden}\n",
        Path("README.ko.md"): "MYSTACK_IMAGE_TAG\ncompose.ghcr.yaml\n",
    }

    with pytest.raises(ImageComposeContractError, match="documentation policy"):
        PublishedImageDocumentationPolicy().validate(documents)
