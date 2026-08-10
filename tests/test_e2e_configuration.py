from __future__ import annotations

from pathlib import Path

from mystack.aws_protocol import load_configuration

from tests.e2e.conftest import E2ESettings

ROOT = Path(__file__).parents[1]


def test_e2e_compose_file_resolves_from_repository_root() -> None:
    settings = E2ESettings.from_configuration(
        load_configuration(ROOT / "config/runtime/mystack.yaml")
    )

    assert settings.compose_file == ROOT / "compose.yaml"
    assert settings.compose_file.is_file()
