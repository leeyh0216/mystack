"""Durable local Step execution journal and restart reconciliation.

The journal is an emulator recovery boundary, not an AWS persistence contract. It preserves the
official EMR property that Step logs can outlive the runtime process and be copied to ``LogUri``.

References:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
- https://docs.python.org/3/library/os.html#os.replace
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from mystack.aws_protocol.observability import log_event
from mystack.emr.application.ports import RuntimeResult
from mystack.emr.domain import Cluster, Step

from .logs import StepLogPublicationRequest, StepLogPublisher

_LOGGER = logging.getLogger(__name__)
_JOURNAL_FILE = "execution-journal.json"
_PUBLICATION_FILE = "log-publication.json"


class JournalPolicy(Protocol):
    retention_seconds: float


@dataclass(frozen=True, slots=True)
class StepExecutionRecord:
    schema_version: int
    cluster_id: str
    cluster_name: str
    release_label: str
    step_id: str
    step_name: str
    log_uri: str | None
    state: str
    started_at_epoch_seconds: float
    completed_at_epoch_seconds: float | None
    process_started: bool
    exit_code: int | None
    reason: str
    work_dir: Path

    def publication_request(self) -> StepLogPublicationRequest:
        stdout = self.work_dir / "stdout.log"
        stderr = self.work_dir / "stderr.log"
        return StepLogPublicationRequest(
            cluster_id=self.cluster_id,
            step_id=self.step_id,
            log_uri=self.log_uri,
            work_dir=self.work_dir,
            process_started=self.process_started,
            exit_code=self.exit_code,
            reason=self.reason,
            stdout_file=stdout if stdout.exists() else None,
            stderr_file=stderr if stderr.exists() else None,
        )


class StepExecutionJournal:
    """Persist execution facts and reconcile unfinished log side effects."""

    def __init__(
        self,
        work_root: Path,
        publisher: StepLogPublisher,
        policy: JournalPolicy,
    ) -> None:
        self._work_root = work_root
        self._publisher = publisher
        self._retention_seconds = policy.retention_seconds
        self._lock = asyncio.Lock()

    async def begin(self, cluster: Cluster, step: Step, work_dir: Path) -> None:
        record = StepExecutionRecord(
            schema_version=1,
            cluster_id=cluster.id,
            cluster_name=cluster.name,
            release_label=cluster.release_label,
            step_id=step.id,
            step_name=step.name,
            log_uri=cluster.log_uri,
            state="running",
            started_at_epoch_seconds=time.time(),
            completed_at_epoch_seconds=None,
            process_started=False,
            exit_code=None,
            reason="",
            work_dir=work_dir,
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.begin.before",
            cluster_id=cluster.id,
            step_id=step.id,
            journal_file=str(work_dir / _JOURNAL_FILE),
            side_effect=True,
        )
        await self._write(record)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.begin.after",
            cluster_id=cluster.id,
            step_id=step.id,
            side_effect=True,
        )

    async def complete(
        self,
        cluster: Cluster,
        step: Step,
        work_dir: Path,
        result: RuntimeResult,
        *,
        process_started: bool,
    ) -> None:
        previous = await self._read(work_dir / _JOURNAL_FILE)
        record = StepExecutionRecord(
            schema_version=1,
            cluster_id=cluster.id,
            cluster_name=cluster.name,
            release_label=cluster.release_label,
            step_id=step.id,
            step_name=step.name,
            log_uri=cluster.log_uri,
            state=(
                "cancelled"
                if str(step.state) == "CANCEL_PENDING"
                else "completed"
                if result.succeeded
                else "failed"
            ),
            started_at_epoch_seconds=(
                previous.started_at_epoch_seconds if previous else time.time()
            ),
            completed_at_epoch_seconds=time.time(),
            process_started=process_started,
            exit_code=result.exit_code,
            reason=result.reason,
            work_dir=work_dir,
        )
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.complete.before",
            cluster_id=cluster.id,
            step_id=step.id,
            execution_state=record.state,
            side_effect=True,
        )
        await self._write(record)
        await self._publisher.publish(record.publication_request())
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.complete.after",
            cluster_id=cluster.id,
            step_id=step.id,
            execution_state=record.state,
            side_effect=True,
        )

    async def recover(self) -> tuple[StepExecutionRecord, ...]:
        """Mark interrupted work and retry terminal records whose publication is incomplete."""

        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.recovery.before",
            work_root=str(self._work_root),
            retention_seconds=self._retention_seconds,
            side_effect=True,
        )
        recovered: list[StepExecutionRecord] = []
        for record in await self.records():
            current = record
            if current.state == "running":
                current = StepExecutionRecord(
                    **{
                        **asdict(current),
                        "state": "interrupted",
                        "completed_at_epoch_seconds": time.time(),
                        "process_started": (current.work_dir / "stdout.log").exists()
                        or (current.work_dir / "stderr.log").exists(),
                        "reason": "EMR emulator restarted while the Step was running",
                    }
                )
                await self._write(current)
                recovered.append(current)
                log_event(
                    _LOGGER,
                    logging.WARNING,
                    "emr.step_journal.interrupted.recovered",
                    cluster_id=current.cluster_id,
                    step_id=current.step_id,
                    fix_hint=(
                        "Use the Console recovered-log projection or inspect "
                        "execution-journal.json; "
                        "the in-memory boto3 control-plane record is not recreated."
                    ),
                    side_effect=True,
                )
            if current.log_uri is not None and not await self._publication_complete(
                current.work_dir
            ):
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.step_journal.publication_recovery.before",
                    cluster_id=current.cluster_id,
                    step_id=current.step_id,
                    side_effect=True,
                )
                await self._publisher.publish(current.publication_request())
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.step_journal.publication_recovery.after",
                    cluster_id=current.cluster_id,
                    step_id=current.step_id,
                    side_effect=True,
                )
        await self._remove_expired()
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step_journal.recovery.after",
            recovered_interrupted_count=len(recovered),
            side_effect=True,
        )
        return tuple(recovered)

    async def records(self) -> tuple[StepExecutionRecord, ...]:
        if not self._work_root.exists():
            return ()
        paths = await asyncio.to_thread(
            lambda: sorted(self._work_root.glob(f"*/*/{_JOURNAL_FILE}"))
        )
        values = await asyncio.gather(*(self._read(path) for path in paths))
        return tuple(value for value in values if value is not None)

    async def find(self, cluster_id: str, step_id: str) -> StepExecutionRecord | None:
        return await self._read(self._work_root / cluster_id / step_id / _JOURNAL_FILE)

    async def _write(self, record: StepExecutionRecord) -> None:
        target = record.work_dir / _JOURNAL_FILE
        document = asdict(record)
        document["work_dir"] = str(record.work_dir)
        content = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        temporary = target.with_suffix(".tmp")
        async with self._lock:
            record.work_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(temporary.write_text, content, encoding="utf-8")
            await asyncio.to_thread(temporary.replace, target)

    async def _read(self, path: Path) -> StepExecutionRecord | None:
        try:
            document = await asyncio.to_thread(path.read_text, encoding="utf-8")
            value = json.loads(document)
            return StepExecutionRecord(
                schema_version=int(value["schema_version"]),
                cluster_id=str(value["cluster_id"]),
                cluster_name=str(value["cluster_name"]),
                release_label=str(value["release_label"]),
                step_id=str(value["step_id"]),
                step_name=str(value["step_name"]),
                log_uri=str(value["log_uri"]) if value.get("log_uri") is not None else None,
                state=str(value["state"]),
                started_at_epoch_seconds=float(value["started_at_epoch_seconds"]),
                completed_at_epoch_seconds=(
                    float(value["completed_at_epoch_seconds"])
                    if value.get("completed_at_epoch_seconds") is not None
                    else None
                ),
                process_started=bool(value["process_started"]),
                exit_code=int(value["exit_code"]) if value.get("exit_code") is not None else None,
                reason=str(value.get("reason", "")),
                work_dir=path.parent,
            )
        except FileNotFoundError:
            return None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.step_journal.read.failed",
                journal_file=str(path),
                fix_hint=(
                    "Compare execution-journal.json with schema_version 1; retain the file for "
                    "manual recovery and update this adapter if the journal schema changes."
                ),
                exc_info=True,
            )
            return None

    async def _publication_complete(self, work_dir: Path) -> bool:
        try:
            value = json.loads(
                await asyncio.to_thread(
                    (work_dir / _PUBLICATION_FILE).read_text,
                    encoding="utf-8",
                )
            )
            return value.get("status") in {"published", "skipped"}
        except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
            return False

    async def _remove_expired(self) -> None:
        cutoff = time.time() - self._retention_seconds
        for record in await self.records():
            if (
                record.completed_at_epoch_seconds is None
                or record.completed_at_epoch_seconds >= cutoff
            ):
                continue
            if not await self._publication_complete(record.work_dir):
                continue
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.step_journal.retention.remove.before",
                cluster_id=record.cluster_id,
                step_id=record.step_id,
                work_dir=str(record.work_dir),
                side_effect=True,
            )
            await asyncio.to_thread(shutil.rmtree, record.work_dir)
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.step_journal.retention.remove.after",
                cluster_id=record.cluster_id,
                step_id=record.step_id,
                side_effect=True,
            )
