"""Local bootstrap and Spark subprocess adapters with LocalStack S3 resolution.

Official behavior and configuration references:
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-commandrunner.html
- https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html
- https://spark.apache.org/docs/3.5.4/submitting-applications.html
- https://hadoop.apache.org/docs/r3.3.4/hadoop-aws/tools/hadoop-aws/index.html
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from mystack.aws_protocol.observability import log_event, payload_fingerprint
from mystack.emr.application.ports import RuntimeResult
from mystack.emr.domain import BootstrapAction, Cluster, Step

from .journal import StepExecutionJournal

_LOGGER = logging.getLogger(__name__)
_S3_SCHEMES = frozenset({"s3", "s3a", "s3n"})
_SPARK_RESOURCE_OPTIONS = frozenset({"--archives", "--files", "--jars", "--py-files"})
_RESOLVED_COMMAND_FILE = "resolved-command.json"


class ObjectStoreConfiguration(Protocol):
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    s3_path_style: bool


class SparkRuntimeConfiguration(Protocol):
    spark_submit: str
    master: str
    packages: tuple[str, ...]
    conf: tuple[tuple[str, str], ...]
    submit_aliases: tuple[str, ...]
    option_value_names: frozenset[str]


class ReleaseRuntimeConfiguration(Protocol):
    runtime_profile: str


class RuntimePolicyConfiguration(Protocol):
    release_profiles: Mapping[str, ReleaseRuntimeConfiguration]


class EmrRuntimeConfiguration(Protocol):
    work_root: Path
    process_timeout_seconds: float
    bootstrap_timeout_seconds: float
    bootstrap_shell: str
    terminate_grace_seconds: float
    shutdown_timeout_seconds: float
    command_runner_jars: frozenset[str]
    object_store: ObjectStoreConfiguration
    runtimes: Mapping[str, SparkRuntimeConfiguration]
    policy: RuntimePolicyConfiguration


class ArtifactResolver(Protocol):
    """Materialize a runtime artifact without exposing storage-client details."""

    async def materialize(self, uri: str, destination: Path) -> Path: ...


class S3ArtifactStore:
    """Resolve s3:// and local artifacts into an explicit work directory."""

    def __init__(self, settings: ObjectStoreConfiguration) -> None:
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            config=Config(s3={"addressing_style": "path" if settings.s3_path_style else "auto"}),
        )
        self._closed = False

    async def materialize(self, uri: str, destination: Path) -> Path:
        if self._closed:
            raise RuntimeError("EMR artifact store is closed")
        parsed = urlparse(uri)
        destination.mkdir(parents=True, exist_ok=True)
        name = Path(parsed.path).name or "artifact"
        target = destination / name
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.artifact.materialize.before",
            uri_scheme=parsed.scheme or "file",
            source_host=parsed.netloc,
            source_path=parsed.path,
            destination=str(target),
            side_effect=True,
        )
        try:
            if parsed.scheme in _S3_SCHEMES:
                if not parsed.netloc or not parsed.path.lstrip("/"):
                    raise ValueError(f"Invalid S3 URI: {uri!r}")
                await asyncio.to_thread(
                    self._client.download_file,
                    parsed.netloc,
                    parsed.path.lstrip("/"),
                    str(target),
                )
            else:
                source = Path(parsed.path if parsed.scheme == "file" else uri)
                await asyncio.to_thread(shutil.copy2, source, target)
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.artifact.materialize.failed",
                uri_scheme=parsed.scheme or "file",
                source_host=parsed.netloc,
                source_path=parsed.path,
                destination=str(target),
                fix_hint=(
                    "Verify the configured LocalStack endpoint, bucket/key, mounted file, "
                    "credentials, and S3 addressing style."
                ),
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.artifact.materialize.after",
            destination=str(target),
            size_bytes=target.stat().st_size,
            side_effect=True,
        )
        return target

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.artifact_store.close.before",
            side_effect=True,
        )
        await asyncio.to_thread(self._client.close)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.artifact_store.close.after",
            side_effect=True,
        )


@dataclass(frozen=True, slots=True)
class _ProcessOutcome:
    exit_code: int
    stdout_file: Path
    stderr_file: Path


class LocalProcessExecutor:
    def __init__(self, settings: EmrRuntimeConfiguration) -> None:
        self._settings = settings
        self._processes: dict[tuple[str, str], asyncio.subprocess.Process] = {}
        self._cancellations: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def active_process_count(self) -> int:
        return len(self._processes)

    async def execute(
        self,
        *,
        cluster_id: str,
        operation_id: str,
        command: list[str],
        work_dir: Path,
        timeout_seconds: float,
        environment: dict[str, str],
    ) -> _ProcessOutcome:
        async with self._lock:
            if self._closed:
                raise RuntimeError("EMR process executor is closed")
        work_dir.mkdir(parents=True, exist_ok=True)
        stdout_file = work_dir / "stdout.log"
        stderr_file = work_dir / "stderr.log"
        command_fingerprint = payload_fingerprint("\0".join(command).encode())
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.process.start.before",
            cluster_id=cluster_id,
            operation_id=operation_id,
            executable=Path(command[0]).name,
            argument_count=len(command) - 1,
            command_fingerprint=command_fingerprint,
            work_dir=str(work_dir),
            timeout_seconds=timeout_seconds,
            side_effect=True,
        )
        with stdout_file.open("wb") as stdout, stderr_file.open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=work_dir,
                env={**os.environ, **environment},
                stdout=stdout,
                stderr=stderr,
            )
            key = (cluster_id, operation_id)
            async with self._lock:
                self._processes[key] = process
                cancellation_requested = key in self._cancellations
                self._cancellations.discard(key)
                executor_closed = self._closed
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.process.start.after",
                cluster_id=cluster_id,
                operation_id=operation_id,
                pid=process.pid,
                side_effect=True,
            )
            if cancellation_requested or executor_closed:
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.process.cancel.deferred.applied",
                    cluster_id=cluster_id,
                    operation_id=operation_id,
                    pid=process.pid,
                    side_effect=True,
                )
                await self._stop(process)
            try:
                exit_code = await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
            except asyncio.CancelledError:
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.process.owner.cancelled",
                    cluster_id=cluster_id,
                    operation_id=operation_id,
                    pid=process.pid,
                    side_effect=True,
                )
                await self._stop(process)
                raise
            except TimeoutError:
                log_event(
                    _LOGGER,
                    logging.ERROR,
                    "emr.process.timeout",
                    cluster_id=cluster_id,
                    operation_id=operation_id,
                    pid=process.pid,
                    timeout_seconds=timeout_seconds,
                    fix_hint=(
                        "Increase the configured timeout or inspect the process "
                        "thread/task diagnostics."
                    ),
                )
                await self._stop(process)
                exit_code = -1
            finally:
                async with self._lock:
                    self._processes.pop(key, None)
                    self._cancellations.discard(key)
        log_event(
            _LOGGER,
            logging.INFO if exit_code == 0 else logging.ERROR,
            "emr.process.finished",
            cluster_id=cluster_id,
            operation_id=operation_id,
            pid=process.pid,
            exit_code=exit_code,
            stdout_file=str(stdout_file),
            stderr_file=str(stderr_file),
            side_effect=True,
        )
        return _ProcessOutcome(exit_code, stdout_file, stderr_file)

    async def cancel(self, cluster_id: str, operation_id: str) -> None:
        async with self._lock:
            key = (cluster_id, operation_id)
            process = self._processes.get(key)
            executor_closed = self._closed
            if process is None:
                if executor_closed:
                    return
                self._cancellations.add(key)
        if process is None:
            log_event(
                _LOGGER,
                logging.INFO,
                "emr.process.cancel.deferred",
                cluster_id=cluster_id,
                operation_id=operation_id,
                fix_hint=(
                    "The cancellation will be applied atomically when the process is registered."
                ),
                side_effect=True,
            )
            return
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.process.cancel.before",
            cluster_id=cluster_id,
            operation_id=operation_id,
            pid=process.pid,
            side_effect=True,
        )
        await self._stop(process)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.process.cancel.after",
            cluster_id=cluster_id,
            operation_id=operation_id,
            pid=process.pid,
            return_code=process.returncode,
            side_effect=True,
        )

    async def cancel_cluster(self, cluster_id: str) -> None:
        async with self._lock:
            operations = [key[1] for key in self._processes if key[0] == cluster_id]
        for operation_id in operations:
            await self.cancel(cluster_id, operation_id)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            processes = list(reversed(self._processes.values()))
            self._cancellations.clear()
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.process_executor.close.before",
            active_process_count=len(processes),
            shutdown_timeout_seconds=self._settings.shutdown_timeout_seconds,
            side_effect=True,
        )
        if processes:
            try:
                await asyncio.wait_for(
                    self._stop_all(processes),
                    timeout=self._settings.shutdown_timeout_seconds,
                )
            except TimeoutError:
                for process in processes:
                    if process.returncode is None:
                        process.kill()
                await asyncio.gather(*(process.wait() for process in processes))
                log_event(
                    _LOGGER,
                    logging.ERROR,
                    "emr.process_executor.close.timeout",
                    shutdown_timeout_seconds=self._settings.shutdown_timeout_seconds,
                    fix_hint=(
                        "Inspect child-process signal handling and the configured terminate grace."
                    ),
                )
                raise
        async with self._lock:
            self._processes.clear()
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.process_executor.close.after",
            active_process_count=self.active_process_count,
            side_effect=True,
        )

    async def _stop_all(self, processes: list[asyncio.subprocess.Process]) -> None:
        for process in processes:
            await self._stop(process)

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self._settings.terminate_grace_seconds,
            )
        except TimeoutError:
            process.kill()
            await process.wait()


class LocalBootstrapRunner:
    def __init__(
        self,
        settings: EmrRuntimeConfiguration,
        artifacts: ArtifactResolver,
        executor: LocalProcessExecutor,
    ) -> None:
        self._settings = settings
        self._artifacts = artifacts
        self._executor = executor

    async def run(
        self,
        cluster: Cluster,
        actions: tuple[BootstrapAction, ...],
    ) -> RuntimeResult:
        for index, action in enumerate(actions):
            action_id = f"bootstrap-{index}"
            work_dir = self._settings.work_root / cluster.id / action_id
            try:
                script = await self._artifacts.materialize(action.path, work_dir)
                outcome = await self._executor.execute(
                    cluster_id=cluster.id,
                    operation_id=action_id,
                    command=[self._settings.bootstrap_shell, str(script), *action.args],
                    work_dir=work_dir,
                    timeout_seconds=self._settings.bootstrap_timeout_seconds,
                    environment=_aws_environment(self._settings.object_store),
                )
            except Exception as error:
                return RuntimeResult(
                    False,
                    reason=f"Bootstrap action {action.name} failed: {error}",
                )
            if outcome.exit_code != 0:
                return RuntimeResult(
                    False,
                    exit_code=outcome.exit_code,
                    reason=f"Bootstrap action {action.name} exited with {outcome.exit_code}",
                    log_file=str(outcome.stderr_file),
                )
        return RuntimeResult(True, exit_code=0)


class SparkSubmitArtifactMaterializer:
    """Materialize primary and dependency resources without understanding Spark execution."""

    def __init__(self, artifacts: ArtifactResolver) -> None:
        self._artifacts = artifacts

    async def materialize(
        self,
        arguments: list[str],
        *,
        work_dir: Path,
        option_value_names: frozenset[str],
    ) -> list[str]:
        result = list(arguments)
        await self._dependencies(result, work_dir)
        application_index = _application_index(result, option_value_names)
        result[application_index] = await self._resource(
            result[application_index], work_dir / "application"
        )
        return result

    async def _dependencies(self, arguments: list[str], work_dir: Path) -> None:
        index = 0
        while index < len(arguments):
            raw = arguments[index]
            option, separator, inline_value = raw.partition("=")
            if option not in _SPARK_RESOURCE_OPTIONS:
                index += 1
                continue
            if separator:
                resources = await self._resource_list(inline_value, work_dir, option)
                arguments[index] = f"{option}={resources}"
                index += 1
                continue
            if index + 1 >= len(arguments):
                raise ValueError(f"Spark submit option {option} requires a value")
            arguments[index + 1] = await self._resource_list(arguments[index + 1], work_dir, option)
            index += 2

    async def _resource_list(self, value: str, work_dir: Path, option: str) -> str:
        resources = value.split(",")
        materialized = [
            await self._resource(
                resource,
                work_dir / "dependencies" / option.removeprefix("--") / str(index),
            )
            for index, resource in enumerate(resources)
        ]
        return ",".join(materialized)

    async def _resource(self, value: str, destination: Path) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {*_S3_SCHEMES, "file"}:
            return value
        path = await self._artifacts.materialize(value, destination)
        return f"{path}#{parsed.fragment}" if parsed.fragment else str(path)


class LocalSparkStepRunner:
    def __init__(
        self,
        settings: EmrRuntimeConfiguration,
        artifacts: ArtifactResolver,
        executor: LocalProcessExecutor,
        journal: StepExecutionJournal,
    ) -> None:
        self._settings = settings
        self._executor = executor
        self._materializer = SparkSubmitArtifactMaterializer(artifacts)
        self._journal = journal

    async def run(self, cluster: Cluster, step: Step) -> RuntimeResult:
        work_dir = self._settings.work_root / cluster.id / step.id
        try:
            await self._journal.begin(cluster, step, work_dir)
            command = await self._command(cluster, step, work_dir)
            await self._record_resolved_command(cluster, step, work_dir, command)
            outcome = await self._executor.execute(
                cluster_id=cluster.id,
                operation_id=step.id,
                command=command,
                work_dir=work_dir,
                timeout_seconds=self._settings.process_timeout_seconds,
                environment=_aws_environment(self._settings.object_store),
            )
        except Exception as error:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.step.prepare.failed",
                cluster_id=cluster.id,
                step_id=step.id,
                reason_type=type(error).__name__,
                fix_hint=(
                    "Compare HadoopJarStep.Args with the configured command runner aliases "
                    "and the Spark 3.5 submit syntax."
                ),
                exc_info=True,
            )
            result = RuntimeResult(False, reason=f"Unable to prepare Spark step: {error}")
            await self._complete_execution(
                cluster,
                step,
                work_dir,
                result,
                process_started=False,
            )
            return result
        result = RuntimeResult(
            outcome.exit_code == 0,
            exit_code=outcome.exit_code,
            reason=(
                "" if outcome.exit_code == 0 else f"spark-submit exited with {outcome.exit_code}"
            ),
            log_file=str(outcome.stderr_file),
        )
        await self._complete_execution(
            cluster,
            step,
            work_dir,
            result,
            process_started=True,
        )
        return result

    async def cancel(self, cluster_id: str, step_id: str) -> None:
        await self._executor.cancel(cluster_id, step_id)

    async def cleanup(self, cluster_id: str) -> None:
        await self._executor.cancel_cluster(cluster_id)

    async def _complete_execution(
        self,
        cluster: Cluster,
        step: Step,
        work_dir: Path,
        result: RuntimeResult,
        *,
        process_started: bool,
    ) -> None:
        try:
            await self._journal.complete(
                cluster,
                step,
                work_dir,
                result,
                process_started=process_started,
            )
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.step_execution.journal_boundary.failed",
                cluster_id=cluster.id,
                step_id=step.id,
                fix_hint=(
                    "Inspect execution-journal.json and publication-request.json. Journal or "
                    "publication failures must not change the Spark RuntimeResult."
                ),
                exc_info=True,
            )

    async def _command(self, cluster: Cluster, step: Step, work_dir: Path) -> list[str]:
        if step.config.jar not in self._settings.command_runner_jars:
            raise ValueError(f"Unsupported step Jar {step.config.jar!r}")
        if not step.config.args:
            raise ValueError("command-runner step requires Args")
        release = self._settings.policy.release_profiles[cluster.release_label]
        runtime = self._settings.runtimes[release.runtime_profile]
        if step.config.args[0] not in runtime.submit_aliases:
            raise ValueError(f"Unsupported command runner command {step.config.args[0]!r}")
        submit_args = await self._materializer.materialize(
            list(step.config.args[1:]),
            work_dir=work_dir,
            option_value_names=runtime.option_value_names,
        )
        command = [runtime.spark_submit]
        if "--master" not in submit_args:
            command.extend(("--master", runtime.master))
        if runtime.packages and "--packages" not in submit_args:
            command.extend(("--packages", ",".join(runtime.packages)))
        for key, value in (*runtime.conf, *_s3_conf(self._settings.object_store)):
            command.extend(("--conf", f"{key}={value}"))
        for key, value in step.config.properties:
            command.extend(("--conf", f"{key}={value}"))
        if step.config.main_class:
            command.extend(("--class", step.config.main_class))
        command.extend(submit_args)
        return command

    async def _record_resolved_command(
        self,
        cluster: Cluster,
        step: Step,
        work_dir: Path,
        command: list[str],
    ) -> None:
        """Persist the exact argv without leaking its potentially sensitive values into logs."""

        document = {"schema_version": 1, "arguments": command}
        content = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        target = work_dir / _RESOLVED_COMMAND_FILE
        temporary = target.with_suffix(".tmp")
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step.resolved_command.write.before",
            cluster_id=cluster.id,
            step_id=step.id,
            argument_count=len(command),
            command_fingerprint=payload_fingerprint(content.encode()),
            side_effect=True,
        )
        await asyncio.to_thread(temporary.write_text, content, encoding="utf-8")
        await asyncio.to_thread(temporary.replace, target)
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.step.resolved_command.write.after",
            cluster_id=cluster.id,
            step_id=step.id,
            argument_count=len(command),
            side_effect=True,
        )


def _application_index(arguments: list[str], value_options: frozenset[str]) -> int:
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        option = argument.split("=", 1)[0]
        if option in value_options:
            index += 1 if "=" in argument else 2
            continue
        if argument.startswith("-"):
            index += 1
            continue
        return index
    raise ValueError("spark-submit application resource is missing")


def _aws_environment(settings: ObjectStoreConfiguration) -> dict[str, str]:
    return {
        "AWS_ACCESS_KEY_ID": settings.access_key_id,
        "AWS_SECRET_ACCESS_KEY": settings.secret_access_key,
        "AWS_DEFAULT_REGION": settings.region,
        "AWS_REGION": settings.region,
        "AWS_ENDPOINT_URL": settings.endpoint_url,
        "AWS_ENDPOINT_URL_S3": settings.endpoint_url,
    }


def _s3_conf(settings: ObjectStoreConfiguration) -> tuple[tuple[str, str], ...]:
    return (
        ("spark.hadoop.fs.s3a.endpoint", settings.endpoint_url),
        ("spark.hadoop.fs.s3a.path.style.access", str(settings.s3_path_style).lower()),
        (
            "spark.hadoop.fs.s3a.connection.ssl.enabled",
            str(settings.endpoint_url.startswith("https://")).lower(),
        ),
        (
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.EnvironmentVariableCredentialsProvider",
        ),
    )
