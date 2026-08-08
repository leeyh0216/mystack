"""System clock, AWS-style IDs, and asyncio scheduling adapters.

ID format examples are documented by the EMR API:
https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Coroutine
from typing import Any

from mystack.aws_protocol.observability import log_event

_LOGGER = logging.getLogger(__name__)


class SystemClock:
    def now(self) -> float:
        return time.time()


class RandomAwsIds:
    def cluster_id(self) -> str:
        return f"j-{uuid.uuid4().hex[:13].upper()}"

    def step_id(self) -> str:
        return f"s-{uuid.uuid4().hex[:13].upper()}"


class AsyncioTaskScheduler:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self, work: Coroutine[Any, Any, None], name: str) -> None:
        task = asyncio.create_task(work, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._done)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.scheduler.task.started",
            task_name=name,
            active_task_count=len(self._tasks),
            side_effect=True,
        )

    def _done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            outcome = "cancelled"
        elif task.exception() is not None:
            outcome = "failed"
        else:
            outcome = "completed"
        log_event(
            _LOGGER,
            logging.ERROR if outcome == "failed" else logging.INFO,
            "emr.scheduler.task.finished",
            task_name=task.get_name(),
            outcome=outcome,
            active_task_count=len(self._tasks),
            fix_hint=(
                "Inspect the task traceback and EMR state-transition events."
                if outcome == "failed"
                else None
            ),
            exc_info=outcome == "failed",
        )
