"""Versioned startup cluster loading and application-port provisioning contracts.

Official request shape: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html
"""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mystack.aws_protocol import ConfigurationError, LoadedConfiguration, load_configuration
from mystack.emr.adapters.inbound import StartupClusterProvisioner, load_startup_cluster_plan
from mystack.emr.config import EmrSettings


def test_disabled_startup_file_produces_an_empty_plan() -> None:
    plan = load_startup_cluster_plan(None, _settings().policy)

    assert plan.source is None
    assert plan.fingerprint is None
    assert plan.commands == ()


def test_loads_official_run_job_flow_members_before_provisioning(tmp_path: Path) -> None:
    source = tmp_path / "clusters.yaml"
    source.write_text(
        """\
schema_version: 1
clusters:
  - Name: analytics
    ReleaseLabel: emr-7.8.0
    Instances:
      InstanceCount: 1
      KeepJobFlowAliveWhenNoSteps: true
    Applications:
      - Name: Spark
    Tags:
      - Key: environment
        Value: test
""",
        encoding="utf-8",
    )

    plan = load_startup_cluster_plan(source, _settings().policy)

    assert plan.source == str(source.resolve())
    assert plan.fingerprint is not None and len(plan.fingerprint) == 16
    assert len(plan.commands) == 1
    command = plan.commands[0]
    assert command.name == "analytics"
    assert command.keep_alive is True
    assert command.applications == ({"Name": "Spark"},)
    assert command.tags == (("environment", "test"),)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            """\
schema_version: 1
clusters:
  - Name: duplicate
    Instances: {InstanceCount: 1}
  - Name: duplicate
    Instances: {InstanceCount: 1}
""",
            "Duplicate startup cluster Name",
        ),
        (
            """\
schema_version: 1
clusters:
  - Name: unsupported-release
    ReleaseLabel: emr-6.15.0
    Instances: {InstanceCount: 1}
""",
            "unconfigured ReleaseLabel",
        ),
        (
            """\
schema_version: 1
clusters:
  - Name: modeled-but-not-emulated
    Instances: {InstanceCount: 1}
    JobFlowRole: EMR_EC2_DefaultRole
""",
            "modeled but unsupported fields",
        ),
    ],
)
def test_rejects_entire_invalid_plan_before_it_can_be_provisioned(
    tmp_path: Path,
    document: str,
    message: str,
) -> None:
    source = tmp_path / "invalid.yaml"
    source.write_text(document, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_startup_cluster_plan(source, _settings().policy)


@pytest.mark.asyncio
async def test_provisions_in_file_order_through_cluster_command_port(tmp_path: Path) -> None:
    source = tmp_path / "clusters.yaml"
    source.write_text(
        """\
schema_version: 1
clusters:
  - Name: first
    Instances: {InstanceCount: 1}
  - Name: second
    Instances: {InstanceCount: 1}
""",
        encoding="utf-8",
    )
    plan = load_startup_cluster_plan(source, _settings().policy)
    commands = _ClusterCommands()
    provisioner = StartupClusterProvisioner(
        commands,  # type: ignore[arg-type]
        plan,
        region="us-east-1",
        account_id="000000000000",
    )

    result = await provisioner.provision()

    assert [cluster.id for cluster in result] == ["j-1", "j-2"]
    assert commands.calls == [
        ("first", "us-east-1", "000000000000"),
        ("second", "us-east-1", "000000000000"),
    ]


def test_resolves_relative_startup_file_beside_main_configuration(tmp_path: Path) -> None:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["emr"]["startup_clusters_file"] = "clusters/startup.yaml"
    configured = LoadedConfiguration(
        document=document,
        source=str(tmp_path / "mystack.yaml"),
        fingerprint=loaded.fingerprint,
        override_paths=loaded.override_paths,
    )

    assert EmrSettings.from_configuration(configured).startup_clusters_file == (
        tmp_path / "clusters/startup.yaml"
    )


class _ClusterCommands:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def create_cluster(self, command: Any, *, region: str, account_id: str) -> Any:
        self.calls.append((command.name, region, account_id))
        return SimpleNamespace(
            id=f"j-{len(self.calls)}",
            state="STARTING",
        )


def _settings() -> EmrSettings:
    return EmrSettings.from_configuration(load_configuration("config/mystack.yaml"))
