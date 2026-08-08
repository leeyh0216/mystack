"""Construct EMR Step aggregates independently from API and runtime adapters.

Official Step shape: https://docs.aws.amazon.com/emr/latest/APIReference/API_Step.html
"""

from __future__ import annotations

from collections.abc import Iterable

from mystack.emr.domain import StateReason, Step, StepState
from mystack.emr.domain.model import StepSpec, StepTimeline

from .ports import IdGenerator


class StepFactory:
    def __init__(self, ids: IdGenerator) -> None:
        self._ids = ids

    def create(self, specs: Iterable[StepSpec], now: float) -> list[Step]:
        return [
            Step(
                id=self._ids.step_id(),
                name=spec.name,
                config=spec.config,
                action_on_failure=spec.action_on_failure,
                state=StepState.PENDING,
                reason=StateReason("", ""),
                timeline=StepTimeline(creation=now),
            )
            for spec in specs
        ]
