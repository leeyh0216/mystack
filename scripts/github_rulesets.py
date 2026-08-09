#!/usr/bin/env python3
"""Validate and converge Mystack-owned repository rulesets without deleting unknown rules.

Official references:
- https://docs.github.com/en/rest/repos/rules
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

LOGGER = logging.getLogger("mystack.github_rulesets")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/governance/github-rulesets.json"
TOP_FIELDS = frozenset(
    {"schema_version", "command_timeout_seconds", "required_check", "rulesets", "official_sources"}
)
RULESET_FIELDS = frozenset(
    {"name", "target", "enforcement", "bypass_actors", "conditions", "rules"}
)
REQUIRED_RULES = frozenset(
    {
        "deletion",
        "non_fast_forward",
        "required_linear_history",
        "pull_request",
        "required_status_checks",
    }
)
PULL_REQUEST_FIELDS = frozenset(
    {
        "allowed_merge_methods",
        "dismiss_stale_reviews_on_push",
        "require_code_owner_review",
        "require_last_push_approval",
        "required_approving_review_count",
        "required_review_thread_resolution",
    }
)
STATUS_FIELDS = frozenset(
    {
        "do_not_enforce_on_create",
        "required_status_checks",
        "strict_required_status_checks_policy",
    }
)


class RulesetError(RuntimeError):
    """A configured or remote ruleset cannot be safely converged."""


def load_config(path: Path) -> dict[str, Any]:
    LOGGER.info("event=ruleset.config.read.before path=%s", path)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RulesetError(f"cannot read ruleset config path={path}: {error}") from error
    if not isinstance(config, dict) or set(config) != TOP_FIELDS:
        raise RulesetError("ruleset config has unknown or missing top-level fields")
    if config["schema_version"] != 1:
        raise RulesetError("ruleset schema_version must be 1")
    timeout = config["command_timeout_seconds"]
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise RulesetError("ruleset command timeout must be a positive integer")
    sources = config["official_sources"]
    if (
        not isinstance(sources, list)
        or not sources
        or not all(
            isinstance(source, str) and source.startswith("https://docs.github.com/")
            for source in sources
        )
    ):
        raise RulesetError("ruleset official_sources must be GitHub HTTPS documentation")
    _validate_rulesets(config)
    LOGGER.info(
        "event=ruleset.config.read.after path=%s rulesets=%d",
        path,
        len(config["rulesets"]),
    )
    return config


def _validate_rulesets(config: dict[str, Any]) -> None:
    rulesets = config["rulesets"]
    if not isinstance(rulesets, list) or len(rulesets) != 2:
        raise RulesetError("exactly main and develop rulesets are required")
    names: set[str] = set()
    refs: set[str] = set()
    for value in rulesets:
        if not isinstance(value, dict) or set(value) != RULESET_FIELDS:
            raise RulesetError("ruleset has unknown or missing fields")
        if value["name"] in names:
            raise RulesetError("ruleset names must be unique")
        names.add(value["name"])
        if value["target"] != "branch" or value["enforcement"] != "active":
            raise RulesetError("managed rulesets must be active branch rulesets")
        if value["bypass_actors"] != []:
            raise RulesetError("managed rulesets must not contain implicit bypass actors")
        ref_name = value.get("conditions", {}).get("ref_name", {})
        include = ref_name.get("include")
        if not isinstance(include, list) or len(include) != 1 or ref_name.get("exclude") != []:
            raise RulesetError("each managed ruleset must target exactly one branch")
        refs.add(include[0])
        rules = value["rules"]
        types = [rule.get("type") for rule in rules if isinstance(rule, dict)]
        if len(types) != len(set(types)) or frozenset(types) != REQUIRED_RULES:
            raise RulesetError("managed ruleset must contain the exact delivery rule types")
        for rule in rules:
            expected_fields = {"type"}
            if rule["type"] in {"pull_request", "required_status_checks"}:
                expected_fields.add("parameters")
            if set(rule) != expected_fields:
                raise RulesetError(f"rule schema mismatch type={rule['type']}")
        pull_request = next(rule for rule in rules if rule["type"] == "pull_request")
        pull_parameters = pull_request.get("parameters", {})
        if set(pull_parameters) != PULL_REQUEST_FIELDS:
            raise RulesetError("pull_request rule has unknown or missing parameters")
        if pull_parameters["allowed_merge_methods"] != ["squash", "rebase"]:
            raise RulesetError("managed branches allow only squash and rebase merges")
        approvals = pull_parameters["required_approving_review_count"]
        if not isinstance(approvals, int) or isinstance(approvals, bool) or not 0 <= approvals <= 6:
            raise RulesetError("approval count must be configurable from zero through six")
        status = next(rule for rule in rules if rule["type"] == "required_status_checks")
        parameters = status.get("parameters", {})
        if set(parameters) != STATUS_FIELDS:
            raise RulesetError("required_status_checks has unknown or missing parameters")
        if parameters.get("required_status_checks") != [{"context": config["required_check"]}]:
            raise RulesetError("required status check must match config.required_check")
        if parameters.get("strict_required_status_checks_policy") is not True:
            raise RulesetError("required status checks must use strict branch freshness")
    if refs != {"refs/heads/main", "refs/heads/develop"}:
        raise RulesetError("managed rulesets must target main and develop")


def config_report(config: dict[str, Any]) -> dict[str, Any]:
    rulesets = config["rulesets"]
    digest = hashlib.sha256(
        json.dumps(rulesets, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": config["schema_version"],
        "required_check": config["required_check"],
        "rulesets": [value["name"] for value in rulesets],
        "rulesets_sha256": digest,
    }


class GhRulesetGateway:
    def __init__(self, repository: str, *, timeout_seconds: int) -> None:
        if repository.count("/") != 1:
            raise RulesetError("repository must use OWNER/NAME")
        self._repository = repository
        self._timeout_seconds = timeout_seconds

    def list(self) -> list[dict[str, Any]]:
        result = self._run("GET", f"repos/{self._repository}/rulesets")
        if not isinstance(result, list):
            raise RulesetError("GitHub ruleset list must be an array")
        return [value for value in result if isinstance(value, dict)]

    def create(self, payload: dict[str, Any]) -> None:
        self._run("POST", f"repos/{self._repository}/rulesets", payload)

    def update(self, identifier: int, payload: dict[str, Any]) -> None:
        self._run("PUT", f"repos/{self._repository}/rulesets/{identifier}", payload)

    def _run(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        command = ["gh", "api", "--method", method, endpoint]
        if payload is not None:
            command.extend(("--input", "-"))
        LOGGER.info(
            "event=ruleset.github.before method=%s endpoint=%s side_effect=%s",
            method,
            endpoint,
            str(method != "GET").lower(),
        )
        try:
            process = subprocess.run(
                command,
                input=json.dumps(payload) if payload is not None else None,
                text=True,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RulesetError(f"GitHub ruleset command failed: {error}") from error
        LOGGER.info(
            "event=ruleset.github.after method=%s endpoint=%s returncode=%d",
            method,
            endpoint,
            process.returncode,
        )
        if process.returncode != 0:
            raise RulesetError(
                f"GitHub ruleset API failed method={method} endpoint={endpoint}; "
                "fix_hint=verify-admin-permission-and-config-schema"
            )
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError as error:
            raise RulesetError("GitHub ruleset API returned invalid JSON") from error


class RulesetGateway(Protocol):
    def list(self) -> list[dict[str, Any]]: ...

    def create(self, payload: dict[str, Any]) -> None: ...

    def update(self, identifier: int, payload: dict[str, Any]) -> None: ...


def converge(
    config: dict[str, Any], gateway: RulesetGateway, *, dry_run: bool
) -> list[dict[str, Any]]:
    existing_by_name: dict[str, dict[str, Any]] = {}
    for value in gateway.list():
        name = value.get("name")
        if name in existing_by_name:
            raise RulesetError(f"duplicate remote managed ruleset name={name!r}")
        if isinstance(name, str):
            existing_by_name[name] = value
    results = []
    for payload in config["rulesets"]:
        existing = existing_by_name.get(payload["name"])
        action = "create" if existing is None else "update"
        identifier = None if existing is None else existing.get("id")
        LOGGER.info(
            "event=ruleset.converge.before name=%s action=%s dry_run=%s side_effect=%s",
            payload["name"],
            action,
            str(dry_run).lower(),
            str(not dry_run).lower(),
        )
        if not dry_run:
            if action == "create":
                gateway.create(payload)
            elif isinstance(identifier, int):
                gateway.update(identifier, payload)
            else:
                raise RulesetError("existing managed ruleset has no integer id")
        results.append({"name": payload["name"], "action": action, "id": identifier})
        LOGGER.info(
            "event=ruleset.converge.after name=%s action=%s dry_run=%s",
            payload["name"],
            action,
            str(dry_run).lower(),
        )
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    apply = commands.add_parser("apply")
    apply.add_argument("--repository", required=True)
    apply.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "check":
            report: Any = config_report(config)
        else:
            gateway = GhRulesetGateway(
                args.repository,
                timeout_seconds=config["command_timeout_seconds"],
            )
            report = converge(config, gateway, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except RulesetError as error:
        LOGGER.error("event=ruleset.failed message=%s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
