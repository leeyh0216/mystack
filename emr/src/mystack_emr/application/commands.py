"""Technology-neutral EMR application commands.

Request semantics reference: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mystack_emr.domain import BootstrapAction, StepSpec


@dataclass(frozen=True, slots=True)
class CreateCluster:
    name: str
    instance_config: dict[str, Any]
    release_label: str | None
    keep_alive: bool
    termination_protected: bool
    visible_to_all_users: bool
    step_concurrency_level: int
    applications: tuple[dict[str, Any], ...]
    bootstrap_actions: tuple[BootstrapAction, ...]
    steps: tuple[StepSpec, ...]
    tags: tuple[tuple[str, str], ...]
    log_uri: str | None
    service_role: str | None


@dataclass(frozen=True, slots=True)
class AddSteps:
    cluster_id: str
    steps: tuple[StepSpec, ...]
