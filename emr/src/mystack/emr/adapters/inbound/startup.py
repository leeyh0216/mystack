"""Load and provision versioned EMR startup clusters through the normal command port.

The external cluster entries use the official RunJobFlow member names and are validated by the
pinned botocore service model before any aggregate is created:
https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html

Docker bind-mounted file behavior:
https://docs.docker.com/engine/storage/bind-mounts/
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from mystack.aws_protocol import AwsServiceError, AwsServiceModel, ConfigurationError
from mystack.aws_protocol.observability import log_event
from mystack.emr.application.commands import CreateCluster
from mystack.emr.application.use_cases import EmrClusterCommands
from mystack.emr.domain import Cluster

from .aws_shapes import create_cluster_command

_LOGGER = logging.getLogger(__name__)
_ROOT_FIELDS = frozenset({"schema_version", "clusters"})
_SUPPORTED_RUN_JOB_FLOW_FIELDS = frozenset(
    {
        "Applications",
        "BootstrapActions",
        "Instances",
        "LogUri",
        "Name",
        "ReleaseLabel",
        "ServiceRole",
        "StepConcurrencyLevel",
        "Steps",
        "Tags",
        "VisibleToAllUsers",
    }
)


class StartupClusterPolicy(Protocol):
    @property
    def max_active_steps(self) -> int: ...

    @property
    def default_release_label(self) -> str: ...

    @property
    def release_profiles(self) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class StartupClusterPlan:
    source: str | None
    fingerprint: str | None
    commands: tuple[CreateCluster, ...]

    @classmethod
    def disabled(cls) -> StartupClusterPlan:
        return cls(source=None, fingerprint=None, commands=())


def load_startup_cluster_plan(
    path: Path | None,
    policy: StartupClusterPolicy,
) -> StartupClusterPlan:
    if path is None:
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.startup_clusters.load.skipped",
            reason="emr.startup_clusters_file is not configured",
            side_effect=False,
        )
        return StartupClusterPlan.disabled()

    source = path.expanduser().resolve()
    log_event(
        _LOGGER,
        logging.INFO,
        "emr.startup_clusters.load.before",
        source=str(source),
        side_effect=True,
    )
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        root = _mapping(document, "<root>")
        unknown_root = sorted(set(root) - _ROOT_FIELDS)
        if unknown_root:
            raise ConfigurationError(
                f"Startup cluster file has unsupported root fields: {unknown_root}"
            )
        if root.get("schema_version") != 1:
            raise ConfigurationError(
                "Unsupported startup cluster schema_version="
                f"{root.get('schema_version')!r}; expected 1"
            )
        raw_clusters = root.get("clusters")
        if not isinstance(raw_clusters, list):
            raise ConfigurationError("Startup cluster field 'clusters' must be a list")
        commands = _commands(raw_clusters, policy)
    except (OSError, yaml.YAMLError, AwsServiceError, KeyError, TypeError, ValueError) as error:
        log_event(
            _LOGGER,
            logging.ERROR,
            "emr.startup_clusters.load.failed",
            source=str(source),
            reason_type=type(error).__name__,
            fix_hint=(
                "Validate every cluster against the pinned RunJobFlow model, the supported-field "
                "list in adapters/inbound/startup.py, and docs/configuration.md. "
                "No server was exposed."
            ),
            exc_info=True,
        )
        if isinstance(error, ConfigurationError):
            raise
        raise ConfigurationError(f"Invalid EMR startup cluster file {source}: {error}") from error

    fingerprint = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    log_event(
        _LOGGER,
        logging.INFO,
        "emr.startup_clusters.load.after",
        source=str(source),
        fingerprint=fingerprint,
        cluster_count=len(commands),
        side_effect=True,
    )
    return StartupClusterPlan(str(source), fingerprint, commands)


class StartupClusterProvisioner:
    """Submit a fully validated plan through the existing CreateCluster use case."""

    def __init__(
        self,
        commands: EmrClusterCommands,
        plan: StartupClusterPlan,
        *,
        region: str,
        account_id: str,
    ) -> None:
        self._commands = commands
        self._plan = plan
        self._region = region
        self._account_id = account_id

    @property
    def plan(self) -> StartupClusterPlan:
        return self._plan

    async def provision(self) -> tuple[Cluster, ...]:
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.startup_clusters.provision.before",
            source=self._plan.source,
            fingerprint=self._plan.fingerprint,
            cluster_count=len(self._plan.commands),
            side_effect=bool(self._plan.commands),
        )
        clusters: list[Cluster] = []
        try:
            for index, command in enumerate(self._plan.commands):
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.startup_cluster.create.before",
                    source=self._plan.source,
                    definition_index=index,
                    cluster_name=command.name,
                    release_label=command.release_label,
                    initial_step_count=len(command.steps),
                    bootstrap_action_count=len(command.bootstrap_actions),
                    side_effect=True,
                )
                cluster = await self._commands.create_cluster(
                    command,
                    region=self._region,
                    account_id=self._account_id,
                )
                clusters.append(cluster)
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "emr.startup_cluster.create.after",
                    definition_index=index,
                    cluster_name=command.name,
                    cluster_id=cluster.id,
                    cluster_state=cluster.state,
                    side_effect=True,
                )
        except Exception:
            log_event(
                _LOGGER,
                logging.ERROR,
                "emr.startup_clusters.provision.failed",
                source=self._plan.source,
                configured_cluster_count=len(self._plan.commands),
                created_cluster_count=len(clusters),
                fix_hint=(
                    "Inspect the failing CreateCluster event. Startup will close the process-local "
                    "runtime before it becomes healthy, so these records are not externally "
                    "visible."
                ),
                exc_info=True,
            )
            raise
        log_event(
            _LOGGER,
            logging.INFO,
            "emr.startup_clusters.provision.after",
            source=self._plan.source,
            created_cluster_count=len(clusters),
            cluster_ids=[cluster.id for cluster in clusters],
            side_effect=bool(clusters),
        )
        return tuple(clusters)


def _commands(
    raw_clusters: list[object], policy: StartupClusterPolicy
) -> tuple[CreateCluster, ...]:
    model = AwsServiceModel("emr")
    operation = model.operation("RunJobFlow")
    commands: list[CreateCluster] = []
    names: set[str] = set()
    for index, raw_cluster in enumerate(raw_clusters):
        cluster = _mapping(raw_cluster, f"clusters[{index}]")
        unsupported = sorted(set(cluster) - _SUPPORTED_RUN_JOB_FLOW_FIELDS)
        if unsupported:
            raise ConfigurationError(
                f"Startup cluster clusters[{index}] has modeled but unsupported fields: "
                f"{unsupported}"
            )
        try:
            model.validate(operation, dict(cluster))
            command = create_cluster_command(cluster)
        except (AwsServiceError, KeyError, TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Startup cluster clusters[{index}] does not satisfy RunJobFlow: {error}"
            ) from error
        if command.name in names:
            raise ConfigurationError(f"Duplicate startup cluster Name: {command.name!r}")
        names.add(command.name)
        release_label = command.release_label or policy.default_release_label
        if release_label not in policy.release_profiles:
            raise ConfigurationError(
                f"Startup cluster {command.name!r} uses unconfigured ReleaseLabel "
                f"{release_label!r}; configured labels: {sorted(policy.release_profiles)}"
            )
        if len(command.steps) > policy.max_active_steps:
            raise ConfigurationError(
                f"Startup cluster {command.name!r} has {len(command.steps)} Steps; "
                f"configured maximum is {policy.max_active_steps}"
            )
        commands.append(command)
    return tuple(commands)


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"Startup cluster field {path} must be a mapping")
    return value
