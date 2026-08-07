"""EMR cluster and Step aggregates with documented lifecycle invariants.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-work-with-steps.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_ClusterStatus.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStatus.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

from .errors import InvalidStateTransitionError, StepNotFoundError


class ClusterState(StrEnum):
    STARTING = "STARTING"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"
    TERMINATED_WITH_ERRORS = "TERMINATED_WITH_ERRORS"


class StepState(StrEnum):
    PENDING = "PENDING"
    CANCEL_PENDING = "CANCEL_PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class ActionOnFailure(StrEnum):
    TERMINATE_JOB_FLOW = "TERMINATE_JOB_FLOW"
    TERMINATE_CLUSTER = "TERMINATE_CLUSTER"
    CANCEL_AND_WAIT = "CANCEL_AND_WAIT"
    CONTINUE = "CONTINUE"


@dataclass(frozen=True, slots=True)
class StateReason:
    code: str
    message: str = ""


@dataclass(slots=True)
class ClusterTimeline:
    creation: float
    ready: float | None = None
    end: float | None = None


@dataclass(slots=True)
class StepTimeline:
    creation: float
    start: float | None = None
    end: float | None = None


@dataclass(frozen=True, slots=True)
class BootstrapAction:
    name: str
    path: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SparkStepConfig:
    jar: str
    args: tuple[str, ...] = ()
    main_class: str | None = None
    properties: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class StepSpec:
    name: str
    config: SparkStepConfig
    action_on_failure: ActionOnFailure = ActionOnFailure.CONTINUE


@dataclass(slots=True)
class Step:
    id: str
    name: str
    config: SparkStepConfig
    action_on_failure: ActionOnFailure
    state: StepState
    reason: StateReason
    timeline: StepTimeline
    failure_details: dict[str, str] | None = None

    _TRANSITIONS: ClassVar[dict[StepState, frozenset[StepState]]] = {
        StepState.PENDING: frozenset({StepState.RUNNING, StepState.CANCELLED}),
        StepState.RUNNING: frozenset(
            {
                StepState.COMPLETED,
                StepState.FAILED,
                StepState.CANCEL_PENDING,
                StepState.INTERRUPTED,
            }
        ),
        StepState.CANCEL_PENDING: frozenset({StepState.CANCELLED, StepState.INTERRUPTED}),
        StepState.COMPLETED: frozenset(),
        StepState.CANCELLED: frozenset(),
        StepState.FAILED: frozenset(),
        StepState.INTERRUPTED: frozenset(),
    }

    @property
    def terminal(self) -> bool:
        return self.state in {
            StepState.COMPLETED,
            StepState.CANCELLED,
            StepState.FAILED,
            StepState.INTERRUPTED,
        }

    def transition(self, state: StepState, at: float, reason: StateReason) -> None:
        if state not in self._TRANSITIONS[self.state]:
            raise InvalidStateTransitionError(
                f"Step {self.id} cannot transition from {self.state} to {state}"
            )
        self.state = state
        self.reason = reason
        if state is StepState.RUNNING:
            self.timeline.start = at
        if self.terminal:
            self.timeline.end = at


@dataclass(slots=True)
class Cluster:
    id: str
    arn: str
    name: str
    release_label: str
    state: ClusterState
    reason: StateReason
    timeline: ClusterTimeline
    keep_alive: bool
    termination_protected: bool
    visible_to_all_users: bool
    step_concurrency_level: int
    instance_config: dict[str, Any]
    applications: tuple[dict[str, Any], ...] = ()
    bootstrap_actions: tuple[BootstrapAction, ...] = ()
    steps: list[Step] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    log_uri: str | None = None
    service_role: str | None = None

    _TRANSITIONS: ClassVar[dict[ClusterState, frozenset[ClusterState]]] = {
        ClusterState.STARTING: frozenset(
            {
                ClusterState.BOOTSTRAPPING,
                ClusterState.TERMINATING,
                ClusterState.TERMINATED_WITH_ERRORS,
            }
        ),
        ClusterState.BOOTSTRAPPING: frozenset(
            {
                ClusterState.RUNNING,
                ClusterState.TERMINATING,
                ClusterState.TERMINATED_WITH_ERRORS,
            }
        ),
        ClusterState.RUNNING: frozenset(
            {ClusterState.WAITING, ClusterState.TERMINATING, ClusterState.TERMINATED_WITH_ERRORS}
        ),
        ClusterState.WAITING: frozenset(
            {ClusterState.RUNNING, ClusterState.TERMINATING, ClusterState.TERMINATED_WITH_ERRORS}
        ),
        ClusterState.TERMINATING: frozenset(
            {ClusterState.TERMINATED, ClusterState.TERMINATED_WITH_ERRORS}
        ),
        ClusterState.TERMINATED: frozenset(),
        ClusterState.TERMINATED_WITH_ERRORS: frozenset(),
    }

    @property
    def terminal(self) -> bool:
        return self.state in {ClusterState.TERMINATED, ClusterState.TERMINATED_WITH_ERRORS}

    def transition(self, state: ClusterState, at: float, reason: StateReason) -> None:
        if state not in self._TRANSITIONS[self.state]:
            raise InvalidStateTransitionError(
                f"Cluster {self.id} cannot transition from {self.state} to {state}"
            )
        self.state = state
        self.reason = reason
        if state in {ClusterState.RUNNING, ClusterState.WAITING} and self.timeline.ready is None:
            self.timeline.ready = at
        if self.terminal:
            self.timeline.end = at

    def step(self, step_id: str) -> Step:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise StepNotFoundError(self.id, step_id)

    def active_step_count(self) -> int:
        return sum(not step.terminal for step in self.steps)
