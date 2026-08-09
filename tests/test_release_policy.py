"""Branch-aware release authorization contracts.

Official reference:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run
"""

from __future__ import annotations

import pytest

from scripts.release_policy import (
    BindingAction,
    BranchPublicationPolicy,
    PolicyError,
    PublicationAction,
    WorkflowContext,
    decide_binding,
)
from scripts.version import StableVersion

VERSION = StableVersion.parse("1.2.3")
SHA = "1234567890abcdef1234567890abcdef12345678"


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (WorkflowContext("pull_request", "main"), PublicationAction.VALIDATE),
        (WorkflowContext("pull_request", "develop"), PublicationAction.VALIDATE),
        (WorkflowContext("push", "feature/catalog"), PublicationAction.VALIDATE),
        (WorkflowContext("push", "develop"), PublicationAction.VALIDATE),
        (WorkflowContext("push", "main"), PublicationAction.VALIDATE),
        (
            WorkflowContext("workflow_run", "main", "pull_request", "success", "CI"),
            PublicationAction.DENY,
        ),
        (
            WorkflowContext("workflow_run", "main", "push", "failure", "CI"),
            PublicationAction.DENY,
        ),
        (
            WorkflowContext("workflow_run", "feature/catalog", "push", "success", "CI"),
            PublicationAction.DENY,
        ),
        (
            WorkflowContext("workflow_run", "main", "push", "success", "Not CI"),
            PublicationAction.DENY,
        ),
        (WorkflowContext("workflow_dispatch", "main"), PublicationAction.DENY),
    ],
)
def test_event_and_ref_map_to_non_publishing_actions(
    context: WorkflowContext, expected: PublicationAction
) -> None:
    plan = BranchPublicationPolicy().resolve(
        context,
        version=VERSION,
        run_number=42,
        commit_sha=SHA,
    )

    assert plan.action is expected
    assert plan.resolved_version is None


def test_successful_develop_ci_resolves_unique_snapshot_without_git_release() -> None:
    context = WorkflowContext("workflow_run", "develop", "push", "success", "CI")

    plan = BranchPublicationPolicy().resolve(
        context,
        version=VERSION,
        run_number=42,
        commit_sha=SHA,
    )

    assert plan.action is PublicationAction.SNAPSHOT
    assert plan.resolved_version is not None
    assert plan.resolved_version.oci_tag == "v1.2.3-snapshot.42.g12345678"
    assert plan.resolved_version.python_version == "1.2.3.dev42+g12345678"


def test_successful_main_ci_resolves_exact_stable_release() -> None:
    context = WorkflowContext("workflow_run", "main", "push", "success", "CI")

    plan = BranchPublicationPolicy().resolve(
        context,
        version=VERSION,
        run_number=42,
        commit_sha=SHA,
    )

    assert plan.action is PublicationAction.RELEASE
    assert plan.resolved_version is not None
    assert plan.resolved_version.oci_tag == "v1.2.3"
    assert plan.resolved_version.python_version == "1.2.3"


def test_immutable_binding_is_create_resume_or_conflict() -> None:
    assert decide_binding(expected_sha=SHA, actual_sha=None) is BindingAction.CREATE
    assert decide_binding(expected_sha=SHA, actual_sha=SHA.upper()) is BindingAction.RESUME
    with pytest.raises(PolicyError, match="another revision"):
        decide_binding(
            expected_sha=SHA,
            actual_sha="abcdef1234567890abcdef1234567890abcdef12",
        )
    with pytest.raises(PolicyError, match="missing or malformed"):
        decide_binding(expected_sha=SHA, actual_sha="unknown")
