"""Entrypoint configuration must be selected before an application is created.

References:
- https://docs.python.org/3/library/argparse.html
- https://www.uvicorn.org/settings/
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from mystack.aws_protocol import load_configuration

_ENTRYPOINTS = (
    ("mystack.proxy.main", "proxy"),
    ("mystack.emr.main", "emr"),
    ("mystack.glue.main", "glue"),
)


def test_entrypoint_imports_do_not_read_a_default_configuration(tmp_path: Path) -> None:
    loaded = load_configuration()
    timeout = float(loaded.document["tests"]["unit_timeout_seconds"])
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "MYSTACK_CONFIG_FILE" and not key.startswith("MYSTACK__")
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            ";".join(f"import {name}" for name, _section in _ENTRYPOINTS),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(("module_name", "section"), _ENTRYPOINTS)
def test_config_cli_argument_is_applied_before_uvicorn_starts(
    module_name: str,
    section: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = load_configuration()
    module = importlib.import_module(module_name)
    captured: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured.update(app=app, **kwargs)

    monkeypatch.setattr(module.uvicorn, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [module_name, "--config", loaded.source])
    module.run()

    assert captured["app"].title.startswith("Mystack")
    assert captured["port"] == loaded.document[section]["listen"]["port"]
