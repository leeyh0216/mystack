"""Management read model for EMR resources and local Step logs.

This adapter is outside the Domain and translates aggregates into a stable, service-neutral JSON
boundary consumed by the Proxy console. Official log semantics:
https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mystack.aws_protocol.observability import log_event
from mystack.emr.application.use_cases import EmrManagementQueries
from mystack.emr.domain import Cluster, Step

_LOGGER = logging.getLogger(__name__)


class EmrManagementAdapter:
    def __init__(
        self,
        application: EmrManagementQueries,
        *,
        work_root: Path,
        output_tail_bytes: int,
        implemented_operations: frozenset[str],
        model_operation_count: int,
        config_fingerprint: str,
    ) -> None:
        self._application = application
        self._work_root = work_root
        self._output_tail_bytes = output_tail_bytes
        self._implemented_operations = implemented_operations
        self._model_operation_count = model_operation_count
        self._config_fingerprint = config_fingerprint

    async def resources(self) -> dict[str, Any]:
        log_event(_LOGGER, logging.INFO, "emr.management.resources.before")
        clusters, _ = await self._application.list_clusters()
        resources = [_cluster(value) for value in clusters]
        step_count = sum(len(value["steps"]) for value in resources)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.resources.after",
            cluster_count=len(resources),
            step_count=step_count,
        )
        return {
            "schema_version": 1,
            "service": "emr",
            "emulator": {
                "mode": "Spark local mode",
                "config_fingerprint": self._config_fingerprint,
                "notice": "EMR control-plane emulation; no EC2, YARN, or HDFS cluster is created.",
            },
            "compatibility": {
                "classification": "PARTIAL",
                "implemented_operation_count": len(self._implemented_operations),
                "model_operation_count": self._model_operation_count,
                "implemented_operations": sorted(self._implemented_operations),
            },
            "counts": {"clusters": len(resources), "steps": step_count},
            "resources": {"clusters": resources},
        }

    async def logs(self, cluster_id: str, step_id: str) -> dict[str, Any]:
        cluster = await self._application.describe_cluster(cluster_id)
        step = cluster.step(step_id)
        work_dir = self._work_root / cluster.id / step.id
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.logs.before",
            cluster_id=cluster.id,
            step_id=step.id,
            work_dir=str(work_dir),
            output_tail_bytes=self._output_tail_bytes,
            side_effect=True,
        )
        stdout, stderr = await asyncio.gather(
            asyncio.to_thread(_tail, work_dir / "stdout.log", self._output_tail_bytes),
            asyncio.to_thread(_tail, work_dir / "stderr.log", self._output_tail_bytes),
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.logs.after",
            cluster_id=cluster.id,
            step_id=step.id,
            stdout_bytes=stdout[1],
            stderr_bytes=stderr[1],
            side_effect=True,
        )
        return {
            "schema_version": 1,
            "service": "emr",
            "cluster_id": cluster.id,
            "step_id": step.id,
            "step_name": step.name,
            "step_state": step.state,
            "stdout": stdout[0],
            "stderr": stderr[0],
            "stdout_truncated": stdout[2],
            "stderr_truncated": stderr[2],
            "tail_limit_bytes": self._output_tail_bytes,
        }


def _cluster(value: Cluster) -> dict[str, Any]:
    return {
        "id": value.id,
        "arn": value.arn,
        "name": value.name,
        "state": value.state,
        "state_reason": {"code": value.reason.code, "message": value.reason.message},
        "release_label": value.release_label,
        "created_at": _timestamp(value.timeline.creation),
        "ready_at": _timestamp(value.timeline.ready),
        "ended_at": _timestamp(value.timeline.end),
        "keep_alive": value.keep_alive,
        "termination_protected": value.termination_protected,
        "visible_to_all_users": value.visible_to_all_users,
        "applications": list(value.applications),
        "bootstrap_actions": [
            {"name": action.name, "path": action.path, "argument_count": len(action.args)}
            for action in value.bootstrap_actions
        ],
        "tags": value.tags,
        "steps": [_step(step) for step in reversed(value.steps)],
    }


def _step(value: Step) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "state": value.state,
        "state_reason": {"code": value.reason.code, "message": value.reason.message},
        "action_on_failure": value.action_on_failure,
        "created_at": _timestamp(value.timeline.creation),
        "started_at": _timestamp(value.timeline.start),
        "ended_at": _timestamp(value.timeline.end),
        "jar": value.config.jar,
        "main_class": value.config.main_class,
        "argument_count": len(value.config.args),
        "failure_details": value.failure_details,
    }


def _timestamp(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None


def _tail(path: Path, limit: int) -> tuple[str, int, bool]:
    if not path.exists():
        return "", 0, False
    size = path.stat().st_size
    with path.open("rb") as stream:
        if size > limit:
            stream.seek(-limit, 2)
        content = stream.read()
    return content.decode("utf-8", errors="replace"), len(content), size > limit
