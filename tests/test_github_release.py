"""Idempotent GitHub tag/release application service tests.

Official references:
- https://docs.github.com/en/rest/git/tags
- https://docs.github.com/en/rest/releases/releases
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripts.release.github_release import GitHubCommandError, ReleaseTransaction
from scripts.release.release_policy import BindingAction, PolicyError

SHA = "1234567890abcdef1234567890abcdef12345678"
OTHER_SHA = "abcdef1234567890abcdef1234567890abcdef12"


@dataclass
class FakeGateway:
    tag_sha: str | None = None
    has_release: bool = False
    fail_tag_once: bool = False
    fail_release_once: bool = False
    tag_creates: int = 0
    release_creates: int = 0
    hide_created_tag: bool = False

    def tag_commit(self, tag: str) -> str | None:
        return self.tag_sha

    def create_annotated_tag(self, tag: str, commit_sha: str, message: str) -> None:
        self.tag_creates += 1
        self.tag_sha = commit_sha
        if self.hide_created_tag:
            self.tag_sha = None
        if self.fail_tag_once:
            self.fail_tag_once = False
            raise GitHubCommandError("concurrent tag creation")

    def release_exists(self, tag: str) -> bool:
        return self.has_release

    def create_release(self, tag: str, commit_sha: str, body: str) -> None:
        self.release_creates += 1
        self.has_release = True
        if self.fail_release_once:
            self.fail_release_once = False
            raise GitHubCommandError("concurrent release creation")


def test_new_tag_and_release_are_created_once_then_resumed() -> None:
    gateway = FakeGateway()
    transaction = ReleaseTransaction(gateway)

    tag = transaction.ensure_tag(tag="v1.2.3", commit_sha=SHA)
    release = transaction.ensure_release(tag="v1.2.3", commit_sha=SHA, body="images")
    retry = transaction.ensure_release(tag="v1.2.3", commit_sha=SHA, body="images")

    assert tag.action is BindingAction.CREATE
    assert release.action is BindingAction.CREATE
    assert retry.action is BindingAction.RESUME
    assert gateway.tag_creates == 1
    assert gateway.release_creates == 1


def test_existing_tag_on_another_sha_rejects_before_release_mutation() -> None:
    gateway = FakeGateway(tag_sha=OTHER_SHA)

    with pytest.raises(PolicyError, match="another revision"):
        ReleaseTransaction(gateway).ensure_release(
            tag="v1.2.3",
            commit_sha=SHA,
            body="images",
        )

    assert gateway.release_creates == 0


def test_concurrent_same_sha_tag_and_release_creation_become_safe_resume() -> None:
    gateway = FakeGateway(fail_tag_once=True, fail_release_once=True)
    transaction = ReleaseTransaction(gateway)

    tag = transaction.ensure_tag(tag="v1.2.3", commit_sha=SHA)
    release = transaction.ensure_release(tag="v1.2.3", commit_sha=SHA, body="images")

    assert tag.action is BindingAction.RESUME
    assert release.action is BindingAction.RESUME


def test_snapshot_tag_cannot_enter_stable_github_release_transaction() -> None:
    with pytest.raises(ValueError, match="invalid stable version"):
        ReleaseTransaction(FakeGateway()).ensure_tag(
            tag="v1.2.3-snapshot.4.g12345678",
            commit_sha=SHA,
        )


def test_tag_create_is_not_reported_successful_when_reference_cannot_be_read_back() -> None:
    with pytest.raises(GitHubCommandError, match="cannot be read back"):
        ReleaseTransaction(FakeGateway(hide_created_tag=True)).ensure_tag(
            tag="v1.2.3",
            commit_sha=SHA,
        )
