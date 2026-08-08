"""Public Glue protocol and real Glue 5 Spark/Hive/Iceberg interoperability E2E.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://docs.docker.com/reference/cli/docker/compose/exec/
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.e2e
def test_real_glue_spark_hive_and_iceberg_through_public_proxy(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    s3 = aws_clients["s3"]
    glue = aws_clients["glue"]
    suffix = uuid.uuid4().hex
    bucket = f"mystack-glue-e2e-{suffix}"
    database = f"mystack_e2e_{suffix}"
    catalog_name = "mystack"
    s3.create_bucket(Bucket=bucket)

    command = [
        "docker",
        "compose",
        "--file",
        str(e2e_settings.compose_file),
        "exec",
        "--no-TTY",
        e2e_settings.glue_service,
        e2e_settings.glue_spark_submit,
        e2e_settings.glue_catalog_script,
        "--catalog-endpoint",
        e2e_settings.glue_catalog_endpoint_url,
        "--object-store-endpoint",
        e2e_settings.object_store_endpoint_url,
        "--region",
        e2e_settings.region,
        "--catalog-id",
        e2e_settings.catalog_id,
        "--bucket",
        bucket,
        "--database",
        database,
        "--catalog-name",
        catalog_name,
    ]
    completed = subprocess.run(
        command,
        cwd=e2e_settings.compose_file.parent,
        capture_output=True,
        text=True,
        timeout=e2e_settings.timeout_seconds,
        check=False,
    )
    _write_diagnostics(completed, e2e_settings.artifacts_dir)
    assert completed.returncode == 0, completed.stderr[-16000:]
    result_line = next(
        line for line in completed.stdout.splitlines() if line.startswith("MYSTACK_E2E_RESULT=")
    )
    result = json.loads(result_line.partition("=")[2])
    assert result["hive_count"] == 1
    assert result["hive_pruned_count"] == 2
    assert len(result["hive_ddl_partitions"]) == 2
    assert len(result["hive_repair_partitions"]) == 2
    assert result["iceberg_count"] == 2
    assert result["spark_version"].startswith(e2e_settings.glue_expected_spark_version_prefix)

    hive_table = glue.get_table(DatabaseName=result["hive_database"], Name="hive_types")["Table"]
    iceberg_table = glue.get_table(DatabaseName=result["iceberg_database"], Name="iceberg_types")[
        "Table"
    ]
    assert hive_table["StorageDescriptor"]["Columns"][2]["Type"] == "array<string>"
    assert iceberg_table["Parameters"]["table_type"].upper() == "ICEBERG"

    ddl_table = glue.get_table(
        DatabaseName=result["hive_database"],
        Name=result["hive_ddl_table"],
    )["Table"]
    ddl_partitions = glue.get_partitions(
        DatabaseName=result["hive_database"],
        TableName=result["hive_ddl_table"],
    )["Partitions"]
    ddl_by_values = {tuple(value["Values"]): value for value in ddl_partitions}
    assert set(ddl_by_values) == {
        ("2026-08-01", "ap/northeast=2"),
        ("2026-08-20", "west"),
    }
    assert ddl_by_values[("2026-08-20", "west")]["StorageDescriptor"]["Location"].endswith(
        "/location-updated"
    )
    assert ddl_table["VersionId"] == "0"
    assert (
        s3.list_objects_v2(Bucket=bucket, Prefix="hive/hive_partition_ddl/drop-preserved").get(
            "KeyCount",
            0,
        )
        > 0
    )

    repair_partitions = glue.get_partitions(
        DatabaseName=result["hive_database"],
        TableName=result["hive_repair_table"],
    )["Partitions"]
    assert {tuple(value["Values"]) for value in repair_partitions} == {
        ("2026-09-03", "west"),
        ("2026-09-04", "east"),
    }


def _write_diagnostics(
    completed: subprocess.CompletedProcess[str],
    artifacts_dir: Path,
) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "glue-spark.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (artifacts_dir / "glue-spark.stderr.log").write_text(completed.stderr, encoding="utf-8")
