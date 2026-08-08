"""Concurrency-safe in-memory EMR repository.

State semantics reference:
https://docs.aws.amazon.com/emr/latest/APIReference/API_ClusterStatus.html
"""

from __future__ import annotations

import asyncio
import copy
import logging

from mystack.aws_protocol.observability import log_event
from mystack.emr.domain import Cluster
from mystack.emr.domain.errors import ClusterNotFoundError

_LOGGER = logging.getLogger(__name__)


class InMemoryClusterRepository:
    """Process-local repository; returned aggregates are isolated copies."""

    def __init__(self) -> None:
        self._clusters: dict[str, Cluster] = {}
        self._lock = asyncio.Lock()

    async def add(self, cluster: Cluster) -> None:
        self._log("emr.repository.add.before", cluster)
        async with self._lock:
            if cluster.id in self._clusters:
                raise ValueError(f"Cluster {cluster.id!r} already exists")
            self._clusters[cluster.id] = copy.deepcopy(cluster)
        self._log("emr.repository.add.after", cluster)

    async def get(self, cluster_id: str) -> Cluster:
        log_event(
            _LOGGER,
            logging.DEBUG,
            "emr.repository.get.before",
            cluster_id=cluster_id,
            side_effect=False,
        )
        async with self._lock:
            cluster = self._clusters.get(cluster_id)
            if cluster is None:
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "emr.repository.get.not_found",
                    cluster_id=cluster_id,
                    fix_hint="Check that the boto3 call uses a JobFlowId returned by RunJobFlow.",
                )
                raise ClusterNotFoundError(cluster_id)
            result = copy.deepcopy(cluster)
        self._log("emr.repository.get.after", result, side_effect=False)
        return result

    async def save(self, cluster: Cluster) -> None:
        self._log("emr.repository.save.before", cluster)
        async with self._lock:
            if cluster.id not in self._clusters:
                raise ClusterNotFoundError(cluster.id)
            self._clusters[cluster.id] = copy.deepcopy(cluster)
        self._log("emr.repository.save.after", cluster)

    async def list(self) -> list[Cluster]:
        async with self._lock:
            result = copy.deepcopy(list(self._clusters.values()))
        log_event(
            _LOGGER,
            logging.DEBUG,
            "emr.repository.list.after",
            count=len(result),
            side_effect=False,
        )
        return result

    @staticmethod
    def _log(event: str, cluster: Cluster, *, side_effect: bool = True) -> None:
        log_event(
            _LOGGER,
            logging.DEBUG,
            event,
            cluster_id=cluster.id,
            cluster_state=cluster.state,
            step_count=len(cluster.steps),
            side_effect=side_effect,
        )
