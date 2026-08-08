"""Mounted extension wheel installation contracts.

Official pip installation guide:
https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from mystack_aws_protocol import LoadedConfiguration, load_configuration
from mystack_glue.config import GlueSettings
from mystack_glue.extension_bootstrap import install_mounted_extensions


def test_installs_only_explicit_mounted_wheels_without_dependency_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    first = wheels / "first_extension-1.0-py3-none-any.whl"
    second = wheels / "second_extension-1.0-py3-none-any.whl"
    first.touch()
    second.touch()
    settings = _settings(tmp_path, enabled=True)
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("mystack_glue.extension_bootstrap.subprocess.run", fake_run)
    monkeypatch.setattr("mystack_glue.extension_bootstrap._write_path_file", lambda path: None)

    install_mounted_extensions(settings)

    command = captured["command"]
    assert "--no-index" in command
    assert "--no-deps" in command
    assert command[-2:] == [str(first), str(second)]
    assert captured["kwargs"]["timeout"] == 5


def test_disabled_extensions_do_not_scan_or_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, enabled=False)

    def unexpected(*args, **kwargs):
        raise AssertionError("pip must not run when extensions are disabled")

    monkeypatch.setattr("mystack_glue.extension_bootstrap.subprocess.run", unexpected)

    install_mounted_extensions(settings)


def test_install_failure_does_not_expose_subprocess_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "broken_extension-1.0-py3-none-any.whl").touch()
    settings = _settings(tmp_path, enabled=True)
    secret = b"do-not-leak-extension-build-output"

    monkeypatch.setattr(
        "mystack_glue.extension_bootstrap.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout=secret, stderr=secret),
    )

    with pytest.raises(RuntimeError) as captured:
        install_mounted_extensions(settings)

    assert secret.decode() not in str(captured.value)


def test_install_timeout_uses_the_file_driven_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "slow_extension-1.0-py3-none-any.whl").touch()
    settings = _settings(tmp_path, enabled=True)

    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("mystack_glue.extension_bootstrap.subprocess.run", timed_out)

    with pytest.raises(RuntimeError, match="timed out"):
        install_mounted_extensions(settings)


def _settings(tmp_path: Path, *, enabled: bool) -> GlueSettings:
    loaded = load_configuration("config/mystack.yaml")
    document = copy.deepcopy(loaded.document)
    document["glue"]["data_root"] = str(tmp_path / "data")
    document["glue"]["extensions"].update(
        {
            "enabled": enabled,
            "wheels_directory": str(tmp_path / "wheels"),
            "install_directory": str(tmp_path / "installed"),
            "install_timeout_seconds": 5,
        }
    )
    configured = LoadedConfiguration(
        document=document,
        source=loaded.source,
        fingerprint=f"extension-bootstrap-{loaded.fingerprint}",
        override_paths=loaded.override_paths,
    )
    return GlueSettings.from_configuration(configured)
