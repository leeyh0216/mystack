"""Repository governance configuration contracts.

Official reference: https://docs.github.com/en/rest/repos/rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.release.github_rulesets import DEFAULT_CONFIG, config_report, converge, load_config


@dataclass
class FakeGateway:
    existing: list[dict[str, Any]] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)
    updated: list[tuple[int, dict[str, Any]]] = field(default_factory=list)

    def list(self) -> list[dict[str, Any]]:
        return self.existing

    def create(self, payload: dict[str, Any]) -> None:
        self.created.append(payload)

    def update(self, identifier: int, payload: dict[str, Any]) -> None:
        self.updated.append((identifier, payload))


def test_committed_rulesets_require_pr_linear_history_and_required_ci() -> None:
    config = load_config(DEFAULT_CONFIG)
    report = config_report(config)

    assert report["required_check"] == "Required CI"
    assert len(report["rulesets_sha256"]) == 64
    for ruleset in config["rulesets"]:
        types = {rule["type"] for rule in ruleset["rules"]}
        assert {"pull_request", "required_status_checks", "non_fast_forward"} <= types
        assert ruleset["bypass_actors"] == []


def test_dry_run_reports_create_and_update_without_mutation() -> None:
    config = load_config(DEFAULT_CONFIG)
    gateway = FakeGateway(existing=[{"id": 42, "name": "Mystack main delivery"}])

    result = converge(config, gateway, dry_run=True)

    assert [item["action"] for item in result] == ["update", "create"]
    assert gateway.created == []
    assert gateway.updated == []


def test_ruleset_config_path_is_repository_owned() -> None:
    assert DEFAULT_CONFIG == Path(__file__).parents[1] / "config/governance/github-rulesets.json"
