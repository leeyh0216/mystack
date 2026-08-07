"""EMR domain failures mapped to AWS errors only by the inbound adapter.

Reference: https://docs.aws.amazon.com/emr/latest/APIReference/API_InvalidRequestException.html
"""


class EmrDomainError(Exception):
    pass


class ClusterNotFoundError(EmrDomainError):
    def __init__(self, cluster_id: str) -> None:
        self.cluster_id = cluster_id
        super().__init__(f"Cluster {cluster_id!r} does not exist")


class StepNotFoundError(EmrDomainError):
    def __init__(self, cluster_id: str, step_id: str) -> None:
        self.cluster_id = cluster_id
        self.step_id = step_id
        super().__init__(f"Step {step_id!r} does not exist in cluster {cluster_id!r}")


class InvalidStateTransitionError(EmrDomainError):
    pass


class InvalidClusterStateError(EmrDomainError):
    pass


class ActiveStepLimitExceededError(EmrDomainError):
    pass


class UnsupportedReleaseLabelError(EmrDomainError):
    pass
