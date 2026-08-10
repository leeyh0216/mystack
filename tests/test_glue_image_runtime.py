"""Glue image Python-runtime contracts.

Official reference:
- https://spark.apache.org/docs/3.5.4/configuration.html#environment-variables
"""

from __future__ import annotations

from pathlib import Path


def test_glue_spark_uses_the_hash_locked_service_virtualenv() -> None:
    repository = Path(__file__).parents[1]
    dockerfile = (repository / "glue" / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (repository / ".dockerignore").read_text(encoding="utf-8")
    wrapper = (repository / "glue" / "bin" / "mystack-spark-submit").read_text(encoding="utf-8")

    assert "PYSPARK_PYTHON=/opt/mystack/venv/bin/python" in dockerfile
    assert "PYSPARK_DRIVER_PYTHON=/opt/mystack/venv/bin/python" in dockerfile
    assert "MYSTACK_GLUE_SPARK_SUBMIT_BINARY=/usr/local/bin/spark-submit" in dockerfile
    assert "PATH=/opt/mystack/bin:/opt/mystack/venv/bin:${PATH}" in dockerfile
    assert '--conf "spark.pyspark.driver.python=${driver_python}"' in wrapper
    assert '--conf "spark.pyspark.python=${worker_python}"' in wrapper
    assert 'exec "${spark_submit_binary}"' in wrapper
    assert "COPY glue/tests/workloads /opt/mystack/e2e" in dockerfile
    assert "!glue/tests/workloads/**" in dockerignore
