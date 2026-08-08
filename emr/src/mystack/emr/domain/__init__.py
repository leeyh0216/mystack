"""EMR domain model; no framework or infrastructure imports.

Reference: https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from mystack.emr.domain.model import (
    ActionOnFailure,
    BootstrapAction,
    Cluster,
    ClusterState,
    SparkStepConfig,
    StateReason,
    Step,
    StepSpec,
    StepState,
)

__all__ = [
    "ActionOnFailure",
    "BootstrapAction",
    "Cluster",
    "ClusterState",
    "SparkStepConfig",
    "StateReason",
    "Step",
    "StepSpec",
    "StepState",
]
