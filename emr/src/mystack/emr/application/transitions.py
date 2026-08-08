"""Logged EMR aggregate transitions shared by command and driver handlers.

Official lifecycle definitions:
https://docs.aws.amazon.com/emr/latest/APIReference/API_ClusterStatus.html
https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStatus.html
"""

from __future__ import annotations

import logging

from mystack.aws_protocol.observability import log_event
from mystack.emr.application.ports import Clock
from mystack.emr.domain import Cluster, ClusterState, StateReason, Step, StepState

_LOGGER = logging.getLogger(__name__)


class LifecycleTransitions:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def cluster(self, cluster: Cluster, state: ClusterState, reason: StateReason) -> None:
        before = cluster.state
        cluster.transition(state, self._clock.now(), reason)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.cluster.state.transitioned",
            cluster_id=cluster.id,
            state_before=before,
            state_after=state,
            reason=reason.code or reason.message,
        )

    def step(self, step: Step, state: StepState, reason: StateReason) -> None:
        before = step.state
        step.transition(state, self._clock.now(), reason)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step.state.transitioned",
            step_id=step.id,
            state_before=before,
            state_after=state,
            reason_code=reason.code,
            reason_message=reason.message,
        )
