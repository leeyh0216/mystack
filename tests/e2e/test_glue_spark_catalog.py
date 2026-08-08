"""Public Glue protocol and real Glue 5 Spark/Hive/Iceberg interoperability E2E.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://docs.docker.com/reference/cli/docker/compose/exec/
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from test_support.iceberg_metadata import IcebergMetadataDocument


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
    assert set(result["hive_alter_failures"]) == {
        "drop-column",
        "rename-column",
        "change-column-type",
        "rename-table",
    }
    assert result["iceberg_count"] == 2
    assert result["iceberg_evolution_count"] == 2
    assert result["iceberg_evolution_filtered_count"] == 1
    assert result["iceberg_evolution_columns"] == [
        "id",
        "category_name",
        "metric",
        "ratio",
        "amount",
        "ts",
        "event",
        "note",
    ]
    assert result["spark_version"].startswith(e2e_settings.glue_expected_spark_version_prefix)
    contention = _run_iceberg_contention(
        s3,
        e2e_settings,
        bucket=bucket,
        database=result["iceberg_database"],
        table="iceberg_types",
    )
    assert {value["writer"] for value in contention} == {"one", "two"}
    assert max(value["count"] for value in contention) == 4

    hive_table = glue.get_table(DatabaseName=result["hive_database"], Name="hive_types")["Table"]
    iceberg_table = glue.get_table(DatabaseName=result["iceberg_database"], Name="iceberg_types")[
        "Table"
    ]
    assert hive_table["StorageDescriptor"]["Columns"][2]["Type"] == "array<string>"
    assert iceberg_table["Parameters"]["table_type"].upper() == "ICEBERG"
    assert int(iceberg_table["VersionId"]) >= 4
    evolution_table = glue.get_table(
        DatabaseName=result["iceberg_database"],
        Name=result["iceberg_evolution_table"],
    )["Table"]
    assert evolution_table["Parameters"]["table_type"].upper() == "ICEBERG"
    assert not evolution_table.get("PartitionKeys")
    evolution_metadata = IcebergMetadataDocument.load_from_s3(
        s3,
        evolution_table["Parameters"]["metadata_location"],
    )
    _assert_iceberg_evolution_metadata(evolution_metadata)

    altered_table = glue.get_table(
        DatabaseName=result["hive_database"],
        Name=result["hive_alter_table"],
    )["Table"]
    altered_columns = altered_table["StorageDescriptor"]["Columns"]
    assert [(value["Name"], value["Type"]) for value in altered_columns] == [
        ("id", "int"),
        ("payload", "struct<kind:string,tags:array<string>>"),
        ("note", "array<struct<source:string,weight:decimal(10,2)>>"),
    ]
    assert altered_columns[1]["Comment"] == "payload comment"
    assert altered_table["StorageDescriptor"]["Location"].endswith("/relocated")
    serde_parameters = altered_table["StorageDescriptor"]["SerdeInfo"]["Parameters"]
    assert serde_parameters["mystack.contract.serde"] == "true"
    assert serde_parameters["serialization.format"] == "1"
    assert altered_table["Parameters"]["mystack.contract.keep"] == "after"
    assert altered_table["Parameters"]["mystack.contract.added"] == "true"
    assert "mystack.contract.remove" not in altered_table["Parameters"]
    assert int(altered_table["VersionId"]) >= 6
    assert glue.get_partition(
        DatabaseName=result["hive_database"],
        TableName=result["hive_alter_table"],
        PartitionValues=["2026-08-09"],
    )["Partition"]["Values"] == ["2026-08-09"]
    with pytest.raises(glue.exceptions.EntityNotFoundException):
        glue.get_table(
            DatabaseName=result["hive_database"],
            Name=f"{result['hive_alter_table']}_renamed",
        )

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


def _assert_iceberg_evolution_metadata(metadata: IcebergMetadataDocument) -> None:
    assert metadata.all_partition_transforms() >= {
        "identity",
        "bucket[8]",
        "truncate[3]",
        "year",
        "month",
        "day",
        "hour",
        "bucket[16]",
    }
    assert metadata.current_partition_transforms() == {
        "bucket[8]",
        "truncate[3]",
        "year",
        "month",
        "day",
        "bucket[16]",
    }
    assert metadata.top_level_field_names() == [
        "id",
        "category_name",
        "metric",
        "ratio",
        "amount",
        "ts",
        "event",
        "note",
    ]
    assert metadata.field_type("metric") == "long"
    assert metadata.field_type("ratio") == "double"
    assert str(metadata.field_type("amount")).replace(" ", "") == "decimal(12,2)"
    assert metadata.field_type("event.details.status_code") == "int"
    assert metadata.field_type("event.details.message") == "string"
    assert not metadata.has_field("category")
    assert not metadata.has_field("obsolete")
    assert not metadata.has_field("event.details.code")
    assert not metadata.has_field("event.details.temporary")
    assert metadata.identifier_field_names() == {"id"}
    assert metadata.current_sort_fields() == [
        {
            "source_name": "category_name",
            "transform": "identity",
            "direction": "asc",
            "null_order": "nulls-last",
        },
        {
            "source_name": "id",
            "transform": "identity",
            "direction": "desc",
            "null_order": "nulls-first",
        },
    ]


def _run_iceberg_contention(
    s3,
    settings: Any,
    *,
    bucket: str,
    database: str,
    table: str,
) -> list[dict[str, Any]]:
    """Release two separate Glue-image Spark JVMs through an S3 barrier.

    Docker Compose `run` creates one-off containers from the reviewed service definition:
    https://docs.docker.com/reference/cli/docker/compose/run/
    """
    barrier_prefix = f"mystack-e2e/contention/{uuid.uuid4().hex}"
    common = [
        "docker",
        "compose",
        "--file",
        str(settings.compose_file),
        "run",
        "--rm",
        "--no-deps",
        "--entrypoint",
        settings.glue_spark_submit,
        settings.glue_service,
        settings.glue_iceberg_contention_script,
        "--catalog-endpoint",
        settings.glue_catalog_endpoint_url,
        "--object-store-endpoint",
        settings.object_store_endpoint_url,
        "--region",
        settings.region,
        "--catalog-id",
        settings.catalog_id,
        "--bucket",
        bucket,
        "--database",
        database,
        "--table",
        table,
        "--catalog-name",
        "mystack",
        "--barrier-prefix",
        barrier_prefix,
        "--timeout-seconds",
        str(settings.timeout_seconds),
        "--poll-interval-seconds",
        str(settings.poll_interval_seconds),
    ]
    processes = {
        writer: subprocess.Popen(
            [*common, "--writer", writer, "--row-id", str(row_id)],
            cwd=settings.compose_file.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for writer, row_id in (("one", 101), ("two", 102))
    }
    deadline = time.monotonic() + settings.timeout_seconds
    completed: dict[str, subprocess.CompletedProcess[str]] = {}
    try:
        _wait_for_ready_markers(
            s3,
            bucket=bucket,
            prefix=f"{barrier_prefix}/ready/",
            expected=2,
            deadline=deadline,
            poll_interval_seconds=settings.poll_interval_seconds,
            processes=processes,
        )
        s3.put_object(Bucket=bucket, Key=f"{barrier_prefix}/start", Body=b"start")
        for writer, process in processes.items():
            remaining = max(0.1, deadline - time.monotonic())
            stdout, stderr = process.communicate(timeout=remaining)
            completed[writer] = subprocess.CompletedProcess(
                process.args,
                process.returncode,
                stdout,
                stderr,
            )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            "Iceberg contention writers exceeded configured E2E timeout"
        ) from error
    finally:
        for writer, process in processes.items():
            if process.poll() is None:
                process.kill()
            if writer not in completed:
                stdout, stderr = process.communicate(
                    timeout=max(1.0, settings.sdk_read_timeout_seconds)
                )
                completed[writer] = subprocess.CompletedProcess(
                    process.args,
                    process.returncode,
                    stdout,
                    stderr,
                )
        _write_contention_diagnostics(completed, settings.artifacts_dir)

    assert all(value.returncode == 0 for value in completed.values()), "\n".join(
        value.stderr[-16000:] for value in completed.values() if value.returncode != 0
    )
    return [
        json.loads(
            next(
                line
                for line in value.stdout.splitlines()
                if line.startswith("MYSTACK_CONTENTION_RESULT=")
            ).partition("=")[2]
        )
        for value in completed.values()
    ]


def _wait_for_ready_markers(
    s3,
    *,
    bucket: str,
    prefix: str,
    expected: int,
    deadline: float,
    poll_interval_seconds: float,
    processes: dict[str, subprocess.Popen[str]],
) -> None:
    while time.monotonic() < deadline:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if int(response.get("KeyCount", 0)) == expected:
            return
        failed = [writer for writer, process in processes.items() if process.poll() is not None]
        if failed:
            raise AssertionError(f"Iceberg contention writers exited before barrier: {failed}")
        time.sleep(poll_interval_seconds)
    raise AssertionError("Iceberg contention readiness exceeded configured E2E timeout")


def _write_contention_diagnostics(
    completed: dict[str, subprocess.CompletedProcess[str]],
    artifacts_dir: Path,
) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for writer, result in completed.items():
        (artifacts_dir / f"iceberg-contention-{writer}.stdout.log").write_text(
            result.stdout,
            encoding="utf-8",
        )
        (artifacts_dir / f"iceberg-contention-{writer}.stderr.log").write_text(
            result.stderr,
            encoding="utf-8",
        )
