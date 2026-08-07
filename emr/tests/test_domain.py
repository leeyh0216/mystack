"""EMR lifecycle invariant tests.

References:
- https://docs.aws.amazon.com/emr/latest/APIReference/API_ClusterStatus.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStatus.html
"""

import pytest
from mystack_emr.domain import StateReason, Step, StepState
from mystack_emr.domain.errors import InvalidStateTransitionError
from mystack_emr.domain.model import ActionOnFailure, SparkStepConfig, StepTimeline


def test_terminal_step_rejects_further_transitions() -> None:
    step = Step(
        id="s-1",
        name="test",
        config=SparkStepConfig("command-runner.jar"),
        action_on_failure=ActionOnFailure.CONTINUE,
        state=StepState.PENDING,
        reason=StateReason(""),
        timeline=StepTimeline(creation=1.0),
    )
    step.transition(StepState.RUNNING, 2.0, StateReason(""))
    step.transition(StepState.COMPLETED, 3.0, StateReason(""))

    with pytest.raises(InvalidStateTransitionError):
        step.transition(StepState.RUNNING, 4.0, StateReason(""))

    assert step.timeline.start == 2.0
    assert step.timeline.end == 3.0
