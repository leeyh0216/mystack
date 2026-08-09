#!/usr/bin/env python3
"""Create or resume an immutable GitHub tag/release transaction.

This adapter is intentionally separate from branch policy and registry publication.

Official references:
- https://docs.github.com/en/rest/git/tags
- https://docs.github.com/en/rest/git/refs
- https://docs.github.com/en/rest/releases/releases
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from scripts.release_policy import BindingAction, PolicyError, decide_binding
from scripts.version import StableVersion, VersionError

LOGGER = logging.getLogger("mystack.github_release")


class GitHubCommandError(RuntimeError):
    """The bounded GitHub CLI adapter failed."""

    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


class GitHubReleaseGateway(Protocol):
    def tag_commit(self, tag: str) -> str | None: ...

    def create_annotated_tag(self, tag: str, commit_sha: str, message: str) -> None: ...

    def release_exists(self, tag: str) -> bool: ...

    def create_release(self, tag: str, commit_sha: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class TransactionResult:
    resource: str
    action: BindingAction
    tag: str
    commit_sha: str

    def as_dict(self) -> dict[str, str]:
        return {
            "resource": self.resource,
            "action": self.action,
            "tag": self.tag,
            "commit_sha": self.commit_sha,
        }


class ReleaseTransaction:
    """Application service enforcing immutable tag and release retries."""

    def __init__(self, gateway: GitHubReleaseGateway) -> None:
        self._gateway = gateway

    def ensure_tag(self, *, tag: str, commit_sha: str) -> TransactionResult:
        _validate_stable_tag(tag)
        LOGGER.info(
            "event=github.tag.ensure.before tag=%s commit_sha=%s side_effect=pending",
            tag,
            commit_sha,
        )
        existing = self._gateway.tag_commit(tag)
        action = decide_binding(expected_sha=commit_sha, actual_sha=existing)
        if action is BindingAction.CREATE:
            try:
                self._gateway.create_annotated_tag(
                    tag,
                    commit_sha,
                    f"Mystack {tag} release",
                )
            except GitHubCommandError:
                # Resolve a concurrent creator deterministically before failing the retry.
                concurrent = self._gateway.tag_commit(tag)
                if concurrent is None:
                    raise
                decide_binding(expected_sha=commit_sha, actual_sha=concurrent)
                action = BindingAction.RESUME
            else:
                created = self._gateway.tag_commit(tag)
                if created is None:
                    raise GitHubCommandError("created tag reference cannot be read back")
                decide_binding(expected_sha=commit_sha, actual_sha=created)
                action = BindingAction.CREATE
        LOGGER.info(
            "event=github.tag.ensure.after tag=%s commit_sha=%s action=%s side_effect=%s",
            tag,
            commit_sha,
            action,
            str(action is BindingAction.CREATE).lower(),
        )
        return TransactionResult("tag", action, tag, commit_sha)

    def ensure_release(
        self,
        *,
        tag: str,
        commit_sha: str,
        body: str,
    ) -> TransactionResult:
        # A release is safe to resume only after its immutable tag binding is proven.
        self.ensure_tag(tag=tag, commit_sha=commit_sha)
        LOGGER.info(
            "event=github.release.ensure.before tag=%s commit_sha=%s side_effect=pending",
            tag,
            commit_sha,
        )
        if self._gateway.release_exists(tag):
            action = BindingAction.RESUME
        else:
            try:
                self._gateway.create_release(tag, commit_sha, body)
            except GitHubCommandError:
                if not self._gateway.release_exists(tag):
                    raise
                action = BindingAction.RESUME
            else:
                if not self._gateway.release_exists(tag):
                    raise GitHubCommandError("created GitHub Release cannot be read back")
                action = BindingAction.CREATE
        LOGGER.info(
            "event=github.release.ensure.after tag=%s commit_sha=%s action=%s side_effect=%s",
            tag,
            commit_sha,
            action,
            str(action is BindingAction.CREATE).lower(),
        )
        return TransactionResult("release", action, tag, commit_sha)


class GhCliGateway:
    """Bounded outbound adapter for GitHub's documented REST resources."""

    def __init__(self, repository: str, *, timeout_seconds: float) -> None:
        if repository.count("/") != 1 or any(not part for part in repository.split("/")):
            raise GitHubCommandError("repository must use OWNER/NAME")
        if timeout_seconds <= 0:
            raise GitHubCommandError("GitHub command timeout must be positive")
        self._repository = repository
        self._timeout_seconds = timeout_seconds

    def tag_commit(self, tag: str) -> str | None:
        encoded_tag = quote(tag, safe="")
        reference = self._json(
            ("repos", self._repository, "git", "ref", "tags", encoded_tag),
            allow_not_found=True,
        )
        if reference is None:
            return None
        target = reference.get("object", {})
        if target.get("type") == "commit":
            raise GitHubCommandError(
                f"existing release tag {tag} is lightweight; "
                "fix_hint=do-not-replace-the-tag-and-choose-a-new-version"
            )
        if target.get("type") != "tag":
            raise GitHubCommandError(f"unsupported Git tag object type={target.get('type')!r}")
        annotated = self._json(
            ("repos", self._repository, "git", "tags", str(target["sha"])),
        )
        assert annotated is not None
        object_value = annotated.get("object", {})
        if object_value.get("type") != "commit":
            raise GitHubCommandError("annotated release tag must point directly to a commit")
        return str(object_value["sha"])

    def create_annotated_tag(self, tag: str, commit_sha: str, message: str) -> None:
        created = self._json(
            ("repos", self._repository, "git", "tags"),
            method="POST",
            fields={"tag": tag, "message": message, "object": commit_sha, "type": "commit"},
        )
        assert created is not None
        self._json(
            ("repos", self._repository, "git", "refs"),
            method="POST",
            fields={"ref": f"refs/tags/{tag}", "sha": str(created["sha"])},
        )

    def release_exists(self, tag: str) -> bool:
        encoded_tag = quote(tag, safe="")
        return (
            self._json(
                ("repos", self._repository, "releases", "tags", encoded_tag),
                allow_not_found=True,
            )
            is not None
        )

    def create_release(self, tag: str, commit_sha: str, body: str) -> None:
        self._json(
            ("repos", self._repository, "releases"),
            method="POST",
            fields={
                "tag_name": tag,
                "target_commitish": commit_sha,
                "name": tag,
                "body": body,
                "draft": False,
                "prerelease": False,
                "generate_release_notes": True,
                "make_latest": "false",
            },
        )

    def _json(
        self,
        path: Sequence[str],
        *,
        method: str = "GET",
        fields: dict[str, str | bool] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, object] | None:
        endpoint = "/".join(path)
        command = ["gh", "api", "--method", method, endpoint]
        for name, value in (fields or {}).items():
            flag = "-F" if isinstance(value, bool) else "-f"
            rendered = str(value).lower() if isinstance(value, bool) else value
            command.extend((flag, f"{name}={rendered}"))
        LOGGER.info(
            "event=github.api.before method=%s endpoint=%s field_names=%s",
            method,
            endpoint,
            sorted((fields or {}).keys()),
        )
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitHubCommandError(f"GitHub CLI failed endpoint={endpoint}: {error}") from error
        LOGGER.info(
            "event=github.api.after method=%s endpoint=%s returncode=%d",
            method,
            endpoint,
            process.returncode,
        )
        if process.returncode != 0:
            not_found = "HTTP 404" in process.stderr or "(HTTP 404)" in process.stderr
            if allow_not_found and not_found:
                return None
            raise GitHubCommandError(
                f"GitHub API failed method={method} endpoint={endpoint} "
                "fix_hint=inspect-gh-api-response-without-printing-tokens",
                not_found=not_found,
            )
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            raise GitHubCommandError(
                f"GitHub API returned invalid JSON endpoint={endpoint}"
            ) from error
        if not isinstance(result, dict):
            raise GitHubCommandError(f"GitHub API returned non-object JSON endpoint={endpoint}")
        return result


def _validate_stable_tag(tag: str) -> None:
    if StableVersion.parse(tag.removeprefix("v")).tag != tag:
        raise VersionError("release tag must be exact vX.Y.Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    commands = parser.add_subparsers(dest="command", required=True)
    tag = commands.add_parser("ensure-tag")
    tag.add_argument("--tag", required=True)
    tag.add_argument("--sha", required=True)
    release = commands.add_parser("ensure-release")
    release.add_argument("--tag", required=True)
    release.add_argument("--sha", required=True)
    release.add_argument("--body", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    transaction = ReleaseTransaction(
        GhCliGateway(args.repository, timeout_seconds=args.timeout_seconds)
    )
    try:
        if args.command == "ensure-tag":
            result = transaction.ensure_tag(tag=args.tag, commit_sha=args.sha)
        else:
            result = transaction.ensure_release(
                tag=args.tag,
                commit_sha=args.sha,
                body=args.body,
            )
        print(json.dumps(result.as_dict(), sort_keys=True))
        return 0
    except (GitHubCommandError, PolicyError, VersionError) as error:
        LOGGER.error(
            "event=github.release.transaction.failed error_type=%s message=%s "
            "fix_hint=inspect-partial-release-and-rerun-the-same-sha",
            type(error).__name__,
            error,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
