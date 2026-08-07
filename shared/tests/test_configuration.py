"""Configuration loading and override contracts.

Docker configs reference: https://docs.docker.com/reference/compose-file/configs/
"""

from pathlib import Path

import pytest
from mystack_aws_protocol import ConfigurationError, load_configuration


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


def test_schema_rejects_unknown_keys_with_actionable_path(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__PROXY__UNSUPPORTED_OPTION", "true")

    with pytest.raises(ConfigurationError, match=r"proxy.*Additional properties"):
        load_configuration("config/mystack.yaml")


def test_schema_rejects_non_positive_timeout(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__TESTS__E2E_TIMEOUT_SECONDS", "0")

    with pytest.raises(ConfigurationError, match=r"tests\.e2e_timeout_seconds"):
        load_configuration("config/mystack.yaml")


def test_schema_error_redacts_sensitive_override_value(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__LOCALSTACK__SECRET_ACCESS_KEY", "123456789")

    with pytest.raises(ConfigurationError) as captured:
        load_configuration("config/mystack.yaml")

    assert "123456789" not in str(captured.value)
    assert "value does not satisfy the configuration schema" in str(captured.value)
