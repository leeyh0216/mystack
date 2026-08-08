"""EMR container inventory and trusted entrypoint disclosure contracts.

Docker ENTRYPOINT reference: https://docs.docker.com/reference/dockerfile/#entrypoint
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from mystack.emr import runtime_inventory
from mystack.emr.privilege import HadoopPrivilegeDropper


def test_inventory_declares_runtime_paths_without_environment_values(
    monkeypatch,
    tmp_path: Path,
) -> None:
    spark_home = tmp_path / "spark"
    spark_home.mkdir()
    (spark_home / "RELEASE").write_text("Spark 3.5.4 test build\n", encoding="utf-8")
    monkeypatch.setenv("SPARK_HOME", str(spark_home))
    monkeypatch.setenv("JAVA_HOME", "/runtime/java")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:never-log-this@example.invalid")
    monkeypatch.setattr(
        runtime_inventory.pwd,
        "getpwnam",
        lambda name: SimpleNamespace(
            pw_name=name,
            pw_uid=10001,
            pw_gid=10001,
            pw_dir="/home/hadoop",
            pw_shell="/bin/bash",
        ),
    )
    monkeypatch.setattr(runtime_inventory, "_os_release", lambda: {"id": "amzn"})
    monkeypatch.setattr(runtime_inventory, "_packages", lambda: [{"name": "boto3", "version": "1"}])
    monkeypatch.setattr(runtime_inventory, "_site_packages", lambda: ["/runtime/site-packages"])
    monkeypatch.setattr(
        runtime_inventory,
        "_ca_paths",
        lambda: {
            "cafile": "/etc/pki/tls/cert.pem",
            "capath": "/etc/pki/tls/certs",
            "openssl_cafile_env": "SSL_CERT_FILE",
            "openssl_capath_env": "SSL_CERT_DIR",
        },
    )
    monkeypatch.setattr(runtime_inventory, "_executable", lambda name: f"/runtime/bin/{name}")
    monkeypatch.setattr(runtime_inventory, "_version", lambda command: f"{command[0]} version")

    document = runtime_inventory.inventory()
    serialized = json.dumps(document)

    assert document["service_identity"]["user"] == "hadoop"
    assert document["service_identity"]["initialization_user"] == "root"
    assert document["spark"]["release"] == "Spark 3.5.4 test build"
    assert document["process_tools"]["ps"] == "/runtime/bin/ps"
    assert document["java"]["default_trust_store"] == "/runtime/java/lib/security/cacerts"
    assert "HTTPS_PROXY" in document["environment_names"]
    assert "never-log-this" not in serialized


def test_image_entrypoint_sources_hooks_then_execs_privilege_adapter() -> None:
    root = Path(__file__).parents[1]
    entrypoint = (root / "scripts/container/entrypoint.sh").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert 'source "$mystack_script"' in entrypoint
    assert 'exec /usr/local/bin/mystack-emr-run-as-hadoop "${mystack_command[@]}"' in entrypoint
    assert "its contents and environment values were not logged" in entrypoint
    assert 'ENTRYPOINT ["/usr/local/bin/mystack-emr-entrypoint"]' in dockerfile
    assert "procps-ng" in dockerfile
    assert "USER hadoop" not in dockerfile


def test_privilege_adapter_changes_groups_and_replaces_the_process(monkeypatch) -> None:
    identity = SimpleNamespace(pw_name="hadoop", pw_uid=10001, pw_gid=10001)
    current = {"uid": 0, "gid": 0}
    events: list[object] = []
    monkeypatch.setattr("mystack.emr.privilege.pwd.getpwnam", lambda name: identity)
    monkeypatch.setattr("mystack.emr.privilege.os.getuid", lambda: current["uid"])
    monkeypatch.setattr("mystack.emr.privilege.os.getgid", lambda: current["gid"])
    monkeypatch.setattr(
        "mystack.emr.privilege.os.initgroups",
        lambda name, gid: events.append(("initgroups", name, gid)),
    )

    def setgid(value: int) -> None:
        events.append(("setgid", value))
        current["gid"] = value

    def setuid(value: int) -> None:
        events.append(("setuid", value))
        current["uid"] = value

    def execvpe(file: str, arguments: list[str], environment: object) -> None:
        events.append(("execvpe", file, arguments, environment is runtime_inventory.os.environ))
        raise _ExecObserved

    monkeypatch.setattr("mystack.emr.privilege.os.setgid", setgid)
    monkeypatch.setattr("mystack.emr.privilege.os.setuid", setuid)
    monkeypatch.setattr("mystack.emr.privilege.os.execvpe", execvpe)

    with pytest.raises(_ExecObserved):
        HadoopPrivilegeDropper().exec(["mystack-emr", "--config", "/config.yaml"])

    assert events == [
        ("initgroups", "hadoop", 10001),
        ("setgid", 10001),
        ("setuid", 10001),
        ("execvpe", "mystack-emr", ["mystack-emr", "--config", "/config.yaml"], True),
    ]


def test_privilege_adapter_failure_discloses_fix_location_without_command(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr("mystack.emr.privilege.os.getuid", lambda: 0)
    monkeypatch.setattr(
        "mystack.emr.privilege.pwd.getpwnam",
        lambda name: (_ for _ in ()).throw(KeyError(name)),
    )

    with pytest.raises(SystemExit, match="126"):
        HadoopPrivilegeDropper().exec(["do-not-log-this-command", "do-not-log-this-value"])

    event = json.loads(capsys.readouterr().err)
    assert event["event"] == "emr.entrypoint.privilege_drop.failed"
    assert event["level"] == "ERROR"
    assert "timestamp" in event
    assert "do-not-log-this" not in json.dumps(event)


class _ExecObserved(Exception):
    pass
