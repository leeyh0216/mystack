#!/usr/bin/env python3
"""Resolve GitHub event/ref publication policy without performing side effects.

Official references:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
- https://semver.org/
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum

from scripts.release.version import ResolvedVersion, StableVersion, VersionError

LOGGER = logging.getLogger("mystack.release_policy")
_FULL_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


class PolicyError(RuntimeError):
    """A workflow context is not authorized to mutate release state."""


class PublicationAction(StrEnum):
    VALIDATE = "validate"
    SNAPSHOT = "snapshot-publish"
    RELEASE = "release-publish"
    DENY = "deny"


class BindingAction(StrEnum):
    CREATE = "create"
    RESUME = "resume"


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    event_name: str
    ref_name: str
    source_event: str = ""
    conclusion: str = ""
    source_workflow: str = ""


@dataclass(frozen=True, slots=True)
class PublicationPlan:
    action: PublicationAction
    branch: str
    reason: str
    resolved_version: ResolvedVersion | None = None

    def as_dict(self) -> dict[str, str | None]:
        version = self.resolved_version
        return {
            "action": self.action,
            "branch": self.branch,
            "reason": self.reason,
            "stable_version": str(version.stable) if version else None,
            "oci_tag": version.oci_tag if version else None,
            "python_version": version.python_version if version else None,
        }


class BranchPublicationPolicy:
    """Keep CI validation and privileged post-CI publication mutually exclusive."""

    def resolve(
        self,
        context: WorkflowContext,
        *,
        version: StableVersion,
        run_number: int,
        commit_sha: str,
    ) -> PublicationPlan:
        if _FULL_GIT_SHA.fullmatch(commit_sha) is None:
            raise PolicyError(
                "publication commit SHA must contain exactly 40 hexadecimal characters"
            )
        LOGGER.info(
            "event=release.policy.resolve.before event_name=%s ref_name=%s "
            "source_event=%s conclusion=%s source_workflow=%s",
            context.event_name,
            context.ref_name,
            context.source_event,
            context.conclusion,
            context.source_workflow,
        )
        plan = self._resolve(
            context,
            version=version,
            run_number=run_number,
            commit_sha=commit_sha,
        )
        LOGGER.info(
            "event=release.policy.resolve.after action=%s branch=%s reason=%s oci_tag=%s",
            plan.action,
            plan.branch,
            plan.reason,
            plan.resolved_version.oci_tag if plan.resolved_version else "",
        )
        return plan

    def _resolve(
        self,
        context: WorkflowContext,
        *,
        version: StableVersion,
        run_number: int,
        commit_sha: str,
    ) -> PublicationPlan:
        if context.event_name in {"pull_request", "push"}:
            return PublicationPlan(
                PublicationAction.VALIDATE,
                context.ref_name,
                "unprivileged-ci-event",
            )
        if context.event_name != "workflow_run":
            return PublicationPlan(
                PublicationAction.DENY,
                context.ref_name,
                "unsupported-trigger",
            )
        if context.source_workflow != "CI":
            return PublicationPlan(
                PublicationAction.DENY,
                context.ref_name,
                "unexpected-source-workflow",
            )
        if context.conclusion != "success" or context.source_event != "push":
            return PublicationPlan(
                PublicationAction.DENY,
                context.ref_name,
                "source-run-not-successful-direct-push",
            )
        if context.ref_name == "develop":
            return PublicationPlan(
                PublicationAction.SNAPSHOT,
                context.ref_name,
                "successful-develop-ci",
                version.snapshot(run_number=run_number, commit_sha=commit_sha),
            )
        if context.ref_name == "main":
            return PublicationPlan(
                PublicationAction.RELEASE,
                context.ref_name,
                "successful-main-ci",
                version.release(),
            )
        return PublicationPlan(
            PublicationAction.DENY,
            context.ref_name,
            "publication-branch-not-allowed",
        )


def decide_binding(*, expected_sha: str, actual_sha: str | None) -> BindingAction:
    """Decide whether an immutable artifact may be created or safely resumed."""
    if _FULL_GIT_SHA.fullmatch(expected_sha) is None:
        raise PolicyError("expected revision must be a complete hexadecimal Git SHA-1")
    if actual_sha is not None and _FULL_GIT_SHA.fullmatch(actual_sha) is None:
        raise PolicyError(
            "existing revision label is missing or malformed; fix_hint=do-not-overwrite"
        )
    if actual_sha is None:
        return BindingAction.CREATE
    if actual_sha.lower() == expected_sha.lower():
        return BindingAction.RESUME
    raise PolicyError(
        f"immutable artifact is bound to another revision expected={expected_sha} "
        f"actual={actual_sha}; fix_hint=bump-version-or-repair-the-partial-release"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--event-name", required=True)
    plan.add_argument("--ref-name", required=True)
    plan.add_argument("--source-event", default="")
    plan.add_argument("--conclusion", default="")
    plan.add_argument("--source-workflow", default="")
    plan.add_argument("--stable-version", required=True)
    plan.add_argument("--run-number", type=int, required=True)
    plan.add_argument("--sha", required=True)
    binding = commands.add_parser("binding")
    binding.add_argument("--expected-sha", required=True)
    binding.add_argument("--actual-sha")
    return parser


def main() -> int:
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        if args.command == "plan":
            context = WorkflowContext(
                event_name=args.event_name,
                ref_name=args.ref_name,
                source_event=args.source_event,
                conclusion=args.conclusion,
                source_workflow=args.source_workflow,
            )
            plan = BranchPublicationPolicy().resolve(
                context,
                version=StableVersion.parse(args.stable_version),
                run_number=args.run_number,
                commit_sha=args.sha,
            )
            print(json.dumps(plan.as_dict(), sort_keys=True))
            return 2 if plan.action is PublicationAction.DENY else 0
        action = decide_binding(expected_sha=args.expected_sha, actual_sha=args.actual_sha)
        print(json.dumps({"action": action}, sort_keys=True))
        return 0
    except (PolicyError, VersionError) as error:
        LOGGER.error(
            "event=release.policy.failed error_type=%s message=%s",
            type(error).__name__,
            error,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
