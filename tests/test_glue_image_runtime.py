"""Glue image Python-runtime contracts.

Official reference:
- https://spark.apache.org/docs/3.5.4/configuration.html#environment-variables
"""

from __future__ import annotations

from pathlib import Path


def test_glue_spark_uses_the_hash_locked_service_virtualenv() -> None:
    dockerfile = (Path(__file__).parents[1] / "glue" / "Dockerfile").read_text(encoding="utf-8")

    assert "PYSPARK_PYTHON=/opt/mystack/venv/bin/python" in dockerfile
    assert "PYSPARK_DRIVER_PYTHON=/opt/mystack/venv/bin/python" in dockerfile
