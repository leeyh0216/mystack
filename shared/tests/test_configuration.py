"""Configuration loading and override contracts.

Docker configs reference: https://docs.docker.com/reference/compose-file/configs/
"""

from pathlib import Path

from mystack_aws_protocol import load_configuration


def test_nested_environment_override_is_typed(monkeypatch) -> None:
    config_path = Path(__file__).parents[2] / "config" / "mystack.yaml"
    monkeypatch.setenv("MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS", "42.5")
    monkeypatch.setenv("MYSTACK__MANAGEMENT__DIAGNOSTICS__ENABLED", "false")

    loaded = load_configuration(config_path)

    assert loaded.document["proxy"]["request_timeout_seconds"] == 42.5
    assert loaded.document["management"]["diagnostics"]["enabled"] is False
    assert loaded.override_paths == (
        "management.diagnostics.enabled",
        "proxy.request_timeout_seconds",
    )
