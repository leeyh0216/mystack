"""Management read model for EMR resources and local Step logs.

This adapter translates aggregates and durable execution records into the Proxy Console boundary.
The byte-offset endpoint is an emulator extension; the S3 projection follows Amazon EMR's layout.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStatus.html
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from mystack.aws_protocol.observability import log_event
from mystack.emr.application.use_cases import EmrManagementQueries
from mystack.emr.domain import Cluster, Step
from mystack.emr.domain.errors import EmrDomainError

_LOGGER = logging.getLogger(__name__)
_PUBLICATION_FILE = "log-publication.json"
_SAFE_RESOURCE_ID = re.compile(r"[A-Za-z0-9_-]+")
_ACTIVE_STEP_STATES = frozenset({"PENDING", "CANCEL_PENDING", "RUNNING"})


class ExecutionRecord(Protocol):
    cluster_id: str
    cluster_name: str
    release_label: str
    step_id: str
    step_name: str
    log_uri: str | None
    state: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float | None
    exit_code: int | None
    reason: str
    work_dir: Path


class ExecutionJournalQueries(Protocol):
    async def records(self) -> tuple[ExecutionRecord, ...]: ...

    async def find(self, cluster_id: str, step_id: str) -> ExecutionRecord | None: ...


class EmrManagementAdapter:
    def __init__(
        self,
        application: EmrManagementQueries,
        *,
        work_root: Path,
        output_tail_bytes: int,
        live_chunk_bytes: int,
        implemented_operations: frozenset[str],
        model_operation_count: int,
        config_fingerprint: str,
        default_release_label: str,
        release_profiles: dict[str, dict[str, str]],
        startup_cluster_source: str | None = None,
        startup_cluster_fingerprint: str | None = None,
        startup_cluster_count: int = 0,
        execution_journal: ExecutionJournalQueries | None = None,
    ) -> None:
        self._application = application
        self._work_root = work_root
        self._output_tail_bytes = output_tail_bytes
        self._live_chunk_bytes = live_chunk_bytes
        self._implemented_operations = implemented_operations
        self._model_operation_count = model_operation_count
        self._config_fingerprint = config_fingerprint
        self._default_release_label = default_release_label
        self._release_profiles = release_profiles
        self._startup_cluster_source = startup_cluster_source
        self._startup_cluster_fingerprint = startup_cluster_fingerprint
        self._startup_cluster_count = startup_cluster_count
        self._execution_journal = execution_journal

    async def resources(self) -> dict[str, Any]:
        log_event(_LOGGER, logging.INFO, "emr.management.resources.before")
        try:
            clusters, _ = await self._application.list_clusters()
            resources = [_cluster(value) for value in clusters]
            resources.extend(await self._recovered_clusters({value.id for value in clusters}))
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.management.resources.failed",
                fix_hint=(
                    "Inspect the EMR query boundary and execution-journal.json compatibility."
                ),
                exc_info=True,
            )
            raise
        step_count = sum(len(value["steps"]) for value in resources)
        recovered_count = sum(bool(value.get("recovered")) for value in resources)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.resources.after",
            cluster_count=len(resources),
            recovered_cluster_count=recovered_count,
            step_count=step_count,
        )
        return {
            "schema_version": 1,
            "service": "emr",
            "emulator": {
                "mode": "Spark local mode",
                "config_fingerprint": self._config_fingerprint,
                "default_release_label": self._default_release_label,
                "release_profiles": self._release_profiles,
                "startup_clusters": {
                    "source": self._startup_cluster_source,
                    "fingerprint": self._startup_cluster_fingerprint,
                    "configured_count": self._startup_cluster_count,
                },
                "notice": "EMR control-plane emulation; no EC2, YARN, or HDFS cluster is created.",
            },
            "compatibility": {
                "classification": "PARTIAL",
                "implemented_operation_count": len(self._implemented_operations),
                "model_operation_count": self._model_operation_count,
                "implemented_operations": sorted(self._implemented_operations),
            },
            "counts": {
                "clusters": len(resources),
                "steps": step_count,
                "recovered_clusters": recovered_count,
            },
            "resources": {"clusters": resources},
        }

    async def logs(self, cluster_id: str, step_id: str) -> dict[str, Any]:
        _validate_resource_ids(cluster_id, step_id)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.logs.before",
            cluster_id=cluster_id,
            step_id=step_id,
            output_tail_bytes=self._output_tail_bytes,
            side_effect=False,
        )
        try:
            work_dir, step_name, step_state, recovered = await self._identity(cluster_id, step_id)
            stdout, stderr = await asyncio.gather(
                asyncio.to_thread(_tail, work_dir / "stdout.log", self._output_tail_bytes),
                asyncio.to_thread(_tail, work_dir / "stderr.log", self._output_tail_bytes),
            )
            publication = await asyncio.to_thread(_publication, work_dir / _PUBLICATION_FILE)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.management.logs.failed",
                cluster_id=cluster_id,
                step_id=step_id,
                fix_hint=(
                    "Verify the resource IDs, work_root mount, and execution journal schema."
                ),
                side_effect=False,
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.management.logs.after",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_bytes=stdout[1],
            stderr_bytes=stderr[1],
            recovered=recovered,
            log_publication_status=publication["status"],
            side_effect=False,
        )
        return {
            "schema_version": 1,
            "service": "emr",
            "cluster_id": cluster_id,
            "step_id": step_id,
            "step_name": step_name,
            "step_state": step_state,
            "recovered": recovered,
            "stdout": stdout[0],
            "stderr": stderr[0],
            "stdout_truncated": stdout[2],
            "stderr_truncated": stderr[2],
            "tail_limit_bytes": self._output_tail_bytes,
            "log_publication": publication,
        }

    async def log_chunk(
        self,
        cluster_id: str,
        step_id: str,
        *,
        stdout_offset: int,
        stderr_offset: int,
    ) -> dict[str, Any]:
        """Return bounded byte-offset chunks for reconnectable Console streaming."""

        _validate_resource_ids(cluster_id, step_id)
        if stdout_offset < 0 or stderr_offset < 0:
            raise ValueError("log offsets must be non-negative")
        work_dir, _, state, recovered = await self._identity(cluster_id, step_id)
        log_event(
            _LOGGER,
            logging.DEBUG,
            "emr.management.log_chunk.before",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
            chunk_limit_bytes=self._live_chunk_bytes,
            side_effect=False,
        )
        stdout, stderr = await asyncio.gather(
            asyncio.to_thread(
                _chunk, work_dir / "stdout.log", stdout_offset, self._live_chunk_bytes
            ),
            asyncio.to_thread(
                _chunk, work_dir / "stderr.log", stderr_offset, self._live_chunk_bytes
            ),
        )
        publication = await asyncio.to_thread(_publication, work_dir / _PUBLICATION_FILE)
        complete = (
            state not in _ACTIVE_STEP_STATES
            and stdout[3]
            and stderr[3]
            and publication["status"] not in {"pending", "publishing", "retrying"}
        )
        log_event(
            _LOGGER,
            logging.DEBUG,
            "emr.management.log_chunk.after",
            cluster_id=cluster_id,
            step_id=step_id,
            stdout_next_offset=stdout[1],
            stderr_next_offset=stderr[1],
            stdout_bytes=stdout[2],
            stderr_bytes=stderr[2],
            complete=complete,
            recovered=recovered,
            side_effect=False,
        )
        return {
            "schema_version": 1,
            "service": "emr",
            "cluster_id": cluster_id,
            "step_id": step_id,
            "step_state": state,
            "recovered": recovered,
            "stdout": stdout[0],
            "stderr": stderr[0],
            "stdout_next_offset": stdout[1],
            "stderr_next_offset": stderr[1],
            "stdout_bytes": stdout[2],
            "stderr_bytes": stderr[2],
            "chunk_limit_bytes": self._live_chunk_bytes,
            "log_publication": publication,
            "complete": complete,
        }

    async def _identity(
        self,
        cluster_id: str,
        step_id: str,
    ) -> tuple[Path, str, str, bool]:
        try:
            cluster = await self._application.describe_cluster(cluster_id)
            step = cluster.step(step_id)
            return self._work_root / cluster.id / step.id, step.name, str(step.state), False
        except EmrDomainError:
            record = await self._journal_record(cluster_id, step_id)
            if record is None:
                raise
            return record.work_dir, record.step_name, _recovered_step_state(record.state), True

    async def _journal_record(
        self,
        cluster_id: str,
        step_id: str,
    ) -> ExecutionRecord | None:
        if self._execution_journal is None:
            return None
        return await self._execution_journal.find(cluster_id, step_id)

    async def _recovered_clusters(self, active_cluster_ids: set[str]) -> list[dict[str, Any]]:
        if self._execution_journal is None:
            return []
        records = await self._execution_journal.records()
        grouped: dict[str, list[ExecutionRecord]] = {}
        for record in records:
            if record.cluster_id not in active_cluster_ids:
                grouped.setdefault(record.cluster_id, []).append(record)
        return [_recovered_cluster(values) for values in grouped.values()]


def _cluster(value: Cluster) -> dict[str, Any]:
    return {
        "id": value.id,
        "arn": value.arn,
        "name": value.name,
        "state": value.state,
        "state_reason": {"code": value.reason.code, "message": value.reason.message},
        "release_label": value.release_label,
        "log_uri": value.log_uri,
        "service_role": value.service_role,
        "step_concurrency_level": value.step_concurrency_level,
        "instance_config": value.instance_config,
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
        "recovered": False,
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
        "recovered": False,
    }


def _recovered_cluster(records: list[ExecutionRecord]) -> dict[str, Any]:
    latest = max(records, key=lambda value: value.started_at_epoch_seconds)
    started = min(value.started_at_epoch_seconds for value in records)
    ended_values = [
        value.completed_at_epoch_seconds
        for value in records
        if value.completed_at_epoch_seconds is not None
    ]
    steps = sorted(records, key=lambda value: value.started_at_epoch_seconds, reverse=True)
    return {
        "id": latest.cluster_id,
        "arn": None,
        "name": latest.cluster_name,
        "state": "TERMINATED_WITH_ERRORS",
        "state_reason": {
            "code": "EMULATOR_RESTART",
            "message": (
                "Recovered log-only projection; boto3 control-plane state was process-local."
            ),
        },
        "release_label": latest.release_label,
        "log_uri": latest.log_uri,
        "service_role": None,
        "step_concurrency_level": 0,
        "instance_config": {},
        "created_at": _timestamp(started),
        "ready_at": None,
        "ended_at": _timestamp(max(ended_values)) if ended_values else None,
        "keep_alive": False,
        "termination_protected": False,
        "visible_to_all_users": True,
        "applications": [],
        "bootstrap_actions": [],
        "tags": {},
        "recovered": True,
        "steps": [
            {
                "id": value.step_id,
                "name": value.step_name,
                "state": _recovered_step_state(value.state),
                "state_reason": {"code": "EMULATOR_RESTART", "message": value.reason},
                "action_on_failure": "CONTINUE",
                "created_at": _timestamp(value.started_at_epoch_seconds),
                "started_at": _timestamp(value.started_at_epoch_seconds),
                "ended_at": _timestamp(value.completed_at_epoch_seconds),
                "jar": "command-runner.jar",
                "main_class": None,
                "argument_count": 0,
                "failure_details": None,
                "recovered": True,
            }
            for value in steps
        ],
    }


def _recovered_step_state(state: str) -> str:
    return {
        "completed": "COMPLETED",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
        "interrupted": "INTERRUPTED",
        "running": "INTERRUPTED",
    }.get(state, "INTERRUPTED")


def _validate_resource_ids(cluster_id: str, step_id: str) -> None:
    if not _SAFE_RESOURCE_ID.fullmatch(cluster_id) or not _SAFE_RESOURCE_ID.fullmatch(step_id):
        raise ValueError("cluster_id and step_id must contain only letters, digits, '_' or '-'")


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


def _chunk(path: Path, offset: int, limit: int) -> tuple[str, int, int, bool]:
    if not path.exists():
        return "", offset, 0, True
    size = path.stat().st_size
    bounded_offset = min(offset, size)
    with path.open("rb") as stream:
        stream.seek(bounded_offset)
        content = stream.read(limit)
    next_offset = bounded_offset + len(content)
    return content.decode("utf-8", errors="replace"), next_offset, len(content), next_offset >= size


def _publication(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "status": "pending"}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "schema_version": 1,
            "status": "unreadable",
            "error_type": type(error).__name__,
            "fix_hint": "Inspect the local EMR Step log-publication.json record.",
        }
    return value if isinstance(value, dict) else {"schema_version": 1, "status": "unreadable"}
