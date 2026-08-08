"""Image-only Compose policy based on the official Compose specification.

https://docs.docker.com/reference/compose-file/
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.check_ghcr_compose import (
    ImageComposeContractError,
    ImageComposePolicy,
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
