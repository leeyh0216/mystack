"""Configuration loading and override contracts.

Docker configs reference: https://docs.docker.com/reference/compose-file/configs/
"""

from pathlib import Path

import pytest
from mystack.aws_protocol import ConfigurationError, load_configuration


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


def test_glue_fault_injection_is_file_driven_and_disabled_by_default() -> None:
    loaded = load_configuration("config/runtime/mystack.yaml")

    assert loaded.document["glue"]["fault_injection"] == {
        "enabled": False,
        "rules": [],
    }


def test_glue_sqlite_busy_timeout_override_is_typed(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__GLUE__SQLITE__BUSY_TIMEOUT_MILLISECONDS", "7500")

    loaded = load_configuration("config/runtime/mystack.yaml")

    assert loaded.document["glue"]["sqlite"]["busy_timeout_milliseconds"] == 7500


def test_schema_rejects_unknown_keys_with_actionable_path(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__PROXY__UNSUPPORTED_OPTION", "true")

    with pytest.raises(ConfigurationError, match=r"proxy.*Additional properties"):
        load_configuration("config/runtime/mystack.yaml")


def test_schema_rejects_non_positive_timeout(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__TESTS__E2E_TIMEOUT_SECONDS", "0")

    with pytest.raises(ConfigurationError, match=r"tests\.e2e_timeout_seconds"):
        load_configuration("config/runtime/mystack.yaml")


def test_compatibility_collection_timeout_is_file_driven(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", "17.5")

    loaded = load_configuration("config/runtime/mystack.yaml")

    assert loaded.document["tests"]["compatibility_collection_timeout_seconds"] == 17.5


def test_schema_rejects_non_positive_compatibility_collection_timeout(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__TESTS__COMPATIBILITY_COLLECTION_TIMEOUT_SECONDS", "0")

    with pytest.raises(
        ConfigurationError,
        match=r"tests\.compatibility_collection_timeout_seconds",
    ):
        load_configuration("config/runtime/mystack.yaml")


def test_console_refresh_interval_is_typed_and_bounded(monkeypatch) -> None:
    monkeypatch.setenv(
        "MYSTACK__MANAGEMENT__CONSOLE__REFRESH_INTERVAL_SECONDS",
        "0.5",
    )
    loaded = load_configuration("config/runtime/mystack.yaml")
    assert loaded.document["management"]["console"]["refresh_interval_seconds"] == 0.5

    monkeypatch.setenv(
        "MYSTACK__MANAGEMENT__CONSOLE__REFRESH_INTERVAL_SECONDS",
        "0.49",
    )
    with pytest.raises(
        ConfigurationError,
        match=r"management\.console\.refresh_interval_seconds",
    ):
        load_configuration("config/runtime/mystack.yaml")


def test_schema_rejects_removed_glue_extension_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__GLUE__EXTENSIONS__ENABLED", "true")

    with pytest.raises(ConfigurationError, match=r"glue.*Additional properties"):
        load_configuration("config/runtime/mystack.yaml")


def test_schema_rejects_removed_management_authentication_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__MANAGEMENT__DIAGNOSTICS__TOKEN", "removed")

    with pytest.raises(ConfigurationError, match=r"management\.diagnostics.*Additional properties"):
        load_configuration("config/runtime/mystack.yaml")


def test_schema_error_redacts_sensitive_override_value(monkeypatch) -> None:
    monkeypatch.setenv("MYSTACK__LOCALSTACK__SECRET_ACCESS_KEY", "123456789")

    with pytest.raises(ConfigurationError) as captured:
        load_configuration("config/runtime/mystack.yaml")

    assert "123456789" not in str(captured.value)
    assert "value does not satisfy the configuration schema" in str(captured.value)
