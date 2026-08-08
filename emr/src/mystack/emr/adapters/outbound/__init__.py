"""Outbound EMR adapters.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from mystack.emr.adapters.outbound.journal import StepExecutionJournal, StepExecutionRecord
from mystack.emr.adapters.outbound.logs import S3StepLogPublisher
from mystack.emr.adapters.outbound.repository import InMemoryClusterRepository
from mystack.emr.adapters.outbound.runtime import (
    LocalBootstrapRunner,
    LocalProcessExecutor,
    LocalSparkStepRunner,
    S3ArtifactStore,
)
from mystack.emr.adapters.outbound.system import AsyncioTaskScheduler, RandomAwsIds, SystemClock

__all__ = [
    "AsyncioTaskScheduler",
    "InMemoryClusterRepository",
    "LocalBootstrapRunner",
    "LocalProcessExecutor",
    "LocalSparkStepRunner",
    "RandomAwsIds",
    "S3ArtifactStore",
    "S3StepLogPublisher",
    "StepExecutionJournal",
    "StepExecutionRecord",
    "SystemClock",
]
