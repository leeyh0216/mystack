"""Source-pin contracts for the private Glue SQLite driver build.

Reference: https://www.sqlite.org/download.html
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[2]
BUILD_SCRIPT = ROOT / "glue/scripts/build_sqlite_driver.py"


def _builder_module() -> ModuleType:
    name = "mystack_glue_sqlite_builder_test"
    spec = importlib.util.spec_from_file_location(name, BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_build_source_pins_are_complete_and_target_the_wal_fixed_runtime() -> None:
    builder = _builder_module()
    source_pins = json.loads((ROOT / "config/sqlite-runtime.json").read_text(encoding="utf-8"))

    spec = builder.load_spec(ROOT / "config/sqlite-runtime.json")

    assert spec.sqlite_version == source_pins["sqlite"]["version"]
    assert spec.minimum_wal_version == source_pins["sqlite"]["minimum_wal_version"]
    assert tuple(map(int, spec.sqlite_version.split("."))) >= (3, 51, 3)
    assert spec.amalgamation.digest_algorithm == "sha3_256"
    assert spec.amalgamation.filename == Path(source_pins["sqlite"]["amalgamation"]["url"]).name
    assert spec.driver_distribution == source_pins["driver"]["distribution"]
    assert spec.driver_module == source_pins["driver"]["module"]
    assert spec.driver_source.digest_algorithm == "sha256"


def test_build_rejects_source_urls_with_query_data(tmp_path: Path) -> None:
    builder = _builder_module()
    document = json.loads((ROOT / "config/sqlite-runtime.json").read_text(encoding="utf-8"))
    document["sqlite"]["amalgamation"]["url"] += "?credential=must-not-appear"
    config = tmp_path / "sqlite-runtime.json"
    config.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(builder.BuildError, match="clean HTTPS URL"):
        builder.load_spec(config)


def test_build_rejects_a_checksum_mismatch_without_retaining_the_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    builder = _builder_module()
    payload = b"verified-source"
    artifact = builder.SourceArtifact(
        url="https://example.test/sqlite.zip?credential=must-not-appear",
        filename="sqlite.zip",
        digest_algorithm="sha256",
        digest=hashlib.sha256(b"different").hexdigest(),
    )

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback
            self.close()
            return False

    monkeypatch.setattr(
        builder.urllib.request, "urlopen", lambda request, timeout: Response(payload)
    )
    destination = tmp_path / artifact.filename

    with pytest.raises(builder.BuildError, match="Checksum mismatch"):
        builder._download_verified(artifact, destination)

    assert not destination.exists()
    output = capsys.readouterr().out
    assert "credential" not in output
    assert artifact.url not in output
