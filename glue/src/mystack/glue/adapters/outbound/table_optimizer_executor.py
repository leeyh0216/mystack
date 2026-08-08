"""Bounded Spark subprocess adapter for managed Glue Iceberg optimizers.

References:
- https://spark.apache.org/docs/3.5.4/submitting-applications.html
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import signal
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from mystack.aws_protocol.observability import log_event
from mystack.glue.application.ports import TableOptimizerExecutionResult
from mystack.glue.application.table_optimizer_contracts import TableOptimizerWork

_LOGGER = logging.getLogger(__name__)
_RESULT_PREFIX = "MYSTACK_TABLE_OPTIMIZER_RESULT="
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class SparkTableOptimizerExecutorSettings:
    spark_submit: Path
    submit_args: tuple[str, ...]
    work_root: Path
    timeout_seconds: float
    terminate_grace_seconds: float
    catalog_endpoint_url: str
    object_store_endpoint_url: str
    object_store_path_style: bool
    region: str
    access_key_id: str
    secret_access_key: str
    catalog_name: str


class SparkTableOptimizerExecutor:
    """Create one diagnosable run directory and one bounded Spark process per claim."""

    def __init__(self, settings: SparkTableOptimizerExecutorSettings) -> None:
        self._settings = settings
        self._script = Path(__file__).resolve().parents[2] / "runtime" / "table_optimizer_job.py"

    async def execute(self, work: TableOptimizerWork) -> TableOptimizerExecutionResult:
        run_id = _validated_run_id(work.run_id)
        run_directory = self._settings.work_root / run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        work_file = run_directory / "work.json"
        stdout_file = run_directory / "stdout.log"
        stderr_file = run_directory / "stderr.log"
        work_document = {
            "catalog_id": work.key[0],
            "database_name": work.key[1],
            "table_name": work.key[2],
            "optimizer_type": work.key[3],
            "configuration": work.configuration,
            "table_location": work.table_location,
            "optimizer_create_time": work.optimizer_create_time,
        }
        work_file.write_text(
            json.dumps(work_document, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        work_file.chmod(0o600)
        command = [
            str(self._settings.spark_submit),
            *self._settings.submit_args,
            str(self._script),
            "--work-file",
            str(work_file),
            "--catalog-endpoint",
            self._settings.catalog_endpoint_url,
            "--object-store-endpoint",
            self._settings.object_store_endpoint_url,
            "--object-store-path-style",
            str(self._settings.object_store_path_style).lower(),
            "--region",
            self._settings.region,
            "--catalog-name",
            self._settings.catalog_name,
        ]
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.table_optimizer.spark.before",
            run_id=run_id,
            optimizer_type=work.optimizer_type.value,
            executable=str(self._settings.spark_submit),
            submit_arg_count=len(self._settings.submit_args),
            work_fingerprint=hashlib.sha256(work_file.read_bytes()).hexdigest()[:16],
            catalog_endpoint_host=urlsplit(self._settings.catalog_endpoint_url).hostname,
            object_store_endpoint_host=urlsplit(self._settings.object_store_endpoint_url).hostname,
            object_store_path_style=self._settings.object_store_path_style,
            timeout_seconds=self._settings.timeout_seconds,
            stdout_file=str(stdout_file),
            stderr_file=str(stderr_file),
            side_effect=True,
            fix_hint=(
                "If Glue 5, Spark, or Iceberg changes its procedure output, update "
                "mystack.glue.runtime.table_optimizer_job and its result decoder."
            ),
        )
        with stdout_file.open("wb") as stdout, stderr_file.open("wb") as stderr:
            environment = os.environ.copy()
            environment.update(
                {
                    "AWS_ACCESS_KEY_ID": self._settings.access_key_id,
                    "AWS_SECRET_ACCESS_KEY": self._settings.secret_access_key,
                    "AWS_REGION": self._settings.region,
                    "AWS_DEFAULT_REGION": self._settings.region,
                    "AWS_ENDPOINT_URL_GLUE": self._settings.catalog_endpoint_url,
                    "AWS_ENDPOINT_URL_S3": self._settings.object_store_endpoint_url,
                }
            )
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=stdout,
                stderr=stderr,
                env=environment,
                start_new_session=True,
            )
            try:
                return_code = await asyncio.wait_for(
                    process.wait(),
                    timeout=self._settings.timeout_seconds,
                )
            except TimeoutError as error:
                await self._stop_process(process)
                raise TimeoutError(
                    f"Spark optimizer exceeded {self._settings.timeout_seconds} seconds; "
                    f"inspect {stderr_file}"
                ) from error
            except asyncio.CancelledError:
                await asyncio.shield(self._stop_process(process))
                raise
        if return_code != 0:
            raise RuntimeError(
                f"Spark optimizer exited with code {return_code}; inspect {stderr_file}"
            )
        metrics = _read_result(stdout_file)
        log_event(
            _LOGGER,
            logging.INFO,
            "glue.table_optimizer.spark.after",
            run_id=run_id,
            optimizer_type=work.optimizer_type.value,
            metric_names=sorted(metrics),
            stdout_file=str(stdout_file),
            stderr_file=str(stderr_file),
            side_effect=True,
        )
        return TableOptimizerExecutionResult(metrics)

    async def _stop_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        _signal_process_group(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self._settings.terminate_grace_seconds,
            )
        except TimeoutError:
            _signal_process_group(process.pid, signal.SIGKILL)
            await process.wait()


def _validated_run_id(value: str) -> str:
    if not _SAFE_RUN_ID.fullmatch(value):
        raise ValueError("Optimizer run identifier is not filesystem-safe")
    return value


def _signal_process_group(process_id: int, process_signal: signal.Signals) -> None:
    try:
        os.killpg(process_id, process_signal)
    except ProcessLookupError:
        return


def _read_result(stdout_file: Path) -> dict:
    result_line = None
    for line in stdout_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(_RESULT_PREFIX):
            result_line = line
    if result_line is None:
        raise RuntimeError(f"Spark optimizer emitted no result marker; inspect {stdout_file}")
    value = json.loads(result_line.removeprefix(_RESULT_PREFIX))
    if not isinstance(value, dict) or not isinstance(value.get("metrics"), dict):
        raise RuntimeError("Spark optimizer result marker has an invalid shape")
    return dict(value["metrics"])
