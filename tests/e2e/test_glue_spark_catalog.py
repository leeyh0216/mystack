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
from botocore.exceptions import ClientError

from tests.support.compatibility import compatibility_evidence
from tests.support.compatibility_profiles import GLUE_SPARK_HIVE_ICEBERG
from tests.support.iceberg_metadata import IcebergMetadataDocument

_ROW_LEVEL_MODE_PROPERTIES = (
    "write.delete.mode",
    "write.update.mode",
    "write.merge.mode",
)


@pytest.mark.e2e
@compatibility_evidence(
    GLUE_SPARK_HIVE_ICEBERG,
    scenario_ids=(
        "hive-complex-types",
        "hive-partition-pruning",
        "hive-partition-ddl-repair",
        "hive-table-alter",
        "iceberg-open-table-format-input",
        "iceberg-create-append-read-evolve",
        "iceberg-partition-schema-sort-evolution",
        "iceberg-row-level-dml",
        "iceberg-snapshots-refs-procedures",
        "iceberg-managed-table-optimizers",
        "iceberg-rename-drop-purge",
        "iceberg-multi-container-contention",
    ),
    operations={
        "glue": (
            "CreateDatabase",
            "CreateTable",
            "CreateTableOptimizer",
            "DeleteTableOptimizer",
            "GetDatabase",
            "GetTable",
            "ListTableOptimizerRuns",
            "UpdateTable",
        )
    },
    capabilities=(
        "hive-metastore",
        "partition-pruning",
        "partition-ddl",
        "table-alter",
        "iceberg-glue-catalog",
        "iceberg-row-level-dml",
        "iceberg-time-travel",
        "iceberg-maintenance-procedures",
    ),
)
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
    iceberg_database = f"{database}_iceberg"
    glue.create_database(DatabaseInput={"Name": iceberg_database})
    open_table_location = f"s3://{bucket}/iceberg/iceberg_open_table_format"
    glue.create_table(
        DatabaseName=iceberg_database,
        Name="iceberg_open_table_format",
        OpenTableFormatInput={
            "IcebergInput": {
                "MetadataOperation": "CREATE",
                "Version": "2",
                "CreateIcebergTableInput": {
                    "Location": open_table_location,
                    "Schema": {
                        "SchemaId": 0,
                        "Type": "struct",
                        "IdentifierFieldIds": [1],
                        "Fields": [
                            {"Id": 1, "Name": "id", "Type": "long", "Required": True},
                            {
                                "Id": 2,
                                "Name": "category",
                                "Type": "string",
                                "Required": False,
                            },
                        ],
                    },
                    "PartitionSpec": {
                        "SpecId": 0,
                        "Fields": [
                            {
                                "SourceId": 2,
                                "FieldId": 1000,
                                "Name": "category",
                                "Transform": "identity",
                            }
                        ],
                    },
                    "WriteOrder": {
                        "OrderId": 1,
                        "Fields": [
                            {
                                "SourceId": 1,
                                "Transform": "identity",
                                "Direction": "asc",
                                "NullOrder": "nulls-first",
                            }
                        ],
                    },
                    "Properties": {"write.format.default": "parquet"},
                },
            }
        },
    )

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
        "--sdk-timeout-seconds",
        str(e2e_settings.sdk_read_timeout_seconds),
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
    assert result["iceberg_open_table_format_initial_columns"] == ["id", "category"]
    assert result["iceberg_open_table_format_initial_count"] == 1
    assert result["iceberg_open_table_format_evolved_columns"] == ["id", "category", "note"]
    assert result["iceberg_open_table_format_rows"] == [
        {"id": 1, "category": "north", "note": None},
        {"id": 2, "category": "south", "note": "evolved"},
    ]
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
    assert result["iceberg_row_cow_after_overwrite"] == [
        {"id": 1, "category": "north", "amount": 11},
        {"id": 3, "category": "south", "amount": 30},
        {"id": 4, "category": "south", "amount": 40},
        {"id": 5, "category": "north", "amount": 50},
    ]
    assert result["iceberg_row_cow_final"] == [
        {"id": 1, "category": "north", "amount": 111},
        {"id": 3, "category": "south", "amount": 31},
        {"id": 6, "category": "south", "amount": 60},
    ]
    assert result["iceberg_row_mor_final"] == [
        {"id": 10, "category": "north", "amount": 101},
        {"id": 12, "category": "south", "amount": 121},
        {"id": 13, "category": "south", "amount": 130},
    ]
    assert result["iceberg_row_cow_invalid_merge_error"]
    _assert_iceberg_snapshot_result(result)
    _assert_iceberg_lifecycle_result(
        result,
        glue=glue,
        s3=s3,
        bucket=bucket,
    )
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
    open_table = glue.get_table(
        DatabaseName=result["iceberg_database"],
        Name=result["iceberg_open_table_format_table"],
    )["Table"]
    assert int(open_table["VersionId"]) >= 3
    assert open_table["Parameters"]["previous_metadata_location"].startswith(
        f"{open_table_location}/metadata/"
    )
    open_table_metadata = IcebergMetadataDocument.load_from_s3(
        s3,
        open_table["Parameters"]["metadata_location"],
    )
    assert open_table_metadata.top_level_field_names() == ["id", "category", "note"]
    assert open_table_metadata.identifier_field_names() == {"id"}
    assert open_table_metadata.current_partition_transforms() == {"identity"}
    assert open_table_metadata.current_sort_fields()[0]["source_name"] == "id"
    assert open_table_metadata.snapshot_count() == 2
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
    _assert_iceberg_row_level_table(
        glue,
        s3,
        database=result["iceberg_database"],
        table=result["iceberg_row_cow_table"],
        expected_mode="copy-on-write",
        expected_version=6,
        expected_snapshots=6,
        expect_delete_files=False,
    )
    _assert_iceberg_row_level_table(
        glue,
        s3,
        database=result["iceberg_database"],
        table=result["iceberg_row_mor_table"],
        expected_mode="merge-on-read",
        expected_version=4,
        expected_snapshots=4,
        expect_delete_files=True,
    )
    snapshot_table = glue.get_table(
        DatabaseName=result["iceberg_database"],
        Name=result["iceberg_snapshot_table"],
    )["Table"]
    assert int(snapshot_table["VersionId"]) >= 16
    snapshot_metadata = IcebergMetadataDocument.load_from_s3(
        s3,
        snapshot_table["Parameters"]["metadata_location"],
    )
    assert snapshot_metadata.reference_names() == {"main"}
    assert (
        snapshot_metadata.reference_snapshot_id("main") == snapshot_metadata.current_snapshot_id()
    )
    assert result["iceberg_snapshot_branch"] not in snapshot_metadata.snapshot_ids()
    assert snapshot_metadata.snapshot_count() >= 7
    with pytest.raises(ClientError) as orphan_error:
        s3.head_object(Bucket=bucket, Key=result["iceberg_snapshot_orphan_key"])
    assert orphan_error.value.response["Error"]["Code"] in {"404", "NoSuchKey"}

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
    _exercise_managed_table_optimizers(
        glue,
        database=result["iceberg_database"],
        table="iceberg_types",
        table_location=iceberg_table["StorageDescriptor"]["Location"],
        timeout_seconds=e2e_settings.timeout_seconds,
        poll_interval_seconds=e2e_settings.poll_interval_seconds,
    )


def _write_diagnostics(
    completed: subprocess.CompletedProcess[str],
    artifacts_dir: Path,
) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "glue-spark.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (artifacts_dir / "glue-spark.stderr.log").write_text(completed.stderr, encoding="utf-8")


def _exercise_managed_table_optimizers(
    glue,
    *,
    database: str,
    table: str,
    table_location: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    """Run all three official managed optimizer types through the service scheduler.

    Source: https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
    """

    configurations = {
        "compaction": {
            "enabled": True,
            "compactionConfiguration": {
                "icebergConfiguration": {
                    "strategy": "binpack",
                    "minInputFiles": 1,
                    "deleteFileThreshold": 1,
                }
            },
        },
        "retention": {
            "enabled": True,
            "retentionConfiguration": {
                "icebergConfiguration": {
                    "snapshotRetentionPeriodInDays": 1,
                    "numberOfSnapshotsToRetain": 1,
                    "cleanExpiredFiles": False,
                    "runRateInHours": 24,
                }
            },
        },
        "orphan_file_deletion": {
            "enabled": True,
            "orphanFileDeletionConfiguration": {
                "icebergConfiguration": {
                    "orphanFileRetentionPeriodInDays": 1,
                    "location": table_location,
                    "runRateInHours": 24,
                }
            },
        },
    }
    for optimizer_type, configuration in configurations.items():
        glue.create_table_optimizer(
            CatalogId="000000000000",
            DatabaseName=database,
            TableName=table,
            Type=optimizer_type,
            TableOptimizerConfiguration=configuration,
        )
        run = _wait_for_table_optimizer(
            glue,
            database=database,
            table=table,
            optimizer_type=optimizer_type,
            deadline=time.monotonic() + timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        assert run["eventType"] == "completed", run.get("error")
        metric_key = {
            "compaction": "compactionMetrics",
            "retention": "retentionMetrics",
            "orphan_file_deletion": "orphanFileDeletionMetrics",
        }[optimizer_type]
        assert "IcebergMetrics" in run[metric_key]
        glue.delete_table_optimizer(
            CatalogId="000000000000",
            DatabaseName=database,
            TableName=table,
            Type=optimizer_type,
        )


def _wait_for_table_optimizer(
    glue,
    *,
    database: str,
    table: str,
    optimizer_type: str,
    deadline: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    while time.monotonic() < deadline:
        runs = glue.list_table_optimizer_runs(
            CatalogId="000000000000",
            DatabaseName=database,
            TableName=table,
            Type=optimizer_type,
            MaxResults=1,
        )["TableOptimizerRuns"]
        if runs and runs[0]["eventType"] in {"completed", "failed"}:
            return runs[0]
        time.sleep(poll_interval_seconds)
    raise AssertionError(f"Managed Glue optimizer {optimizer_type} exceeded E2E timeout")


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


def _assert_iceberg_snapshot_result(result: dict[str, Any]) -> None:
    first = [{"id": 1, "category": "main", "payload": "one"}]
    main_two = [
        {"id": 1, "category": "main", "payload": "one"},
        {"id": 2, "category": "main", "payload": "two"},
    ]
    branch = [
        {"id": 1, "category": "main", "payload": "one"},
        {"id": 10, "category": "branch", "payload": "ten"},
    ]
    final = [
        {"id": 1, "category": "main", "payload": "one"},
        {"id": 2, "category": "main", "payload": "two"},
        {"id": 3, "category": "main", "payload": "value-3"},
        {"id": 4, "category": "main", "payload": "value-4"},
        {"id": 5, "category": "main", "payload": "value-5"},
        {"id": 10, "category": "branch", "payload": "ten"},
    ]
    assert result["iceberg_snapshot_version_rows"] == first
    assert result["iceberg_snapshot_timestamp_rows"] == first
    assert result["iceberg_snapshot_tag_rows"] == first
    assert result["iceberg_snapshot_main_before_cherry_pick"] == main_two
    assert result["iceberg_snapshot_branch_rows"] == branch
    assert result["iceberg_snapshot_rows_after_rollback"] == first
    assert result["iceberg_snapshot_final_rows"] == final
    assert result["iceberg_snapshot_rows_after_maintenance"] == final
    assert all(int(count) > 0 for count in result["iceberg_snapshot_metadata_counts"].values())
    assert result["iceberg_snapshot_rollback"] == {
        "previous_snapshot_id": result["iceberg_snapshot_two"],
        "current_snapshot_id": result["iceberg_snapshot_one"],
    }
    assert result["iceberg_snapshot_set_current"] == {
        "previous_snapshot_id": result["iceberg_snapshot_one"],
        "current_snapshot_id": result["iceberg_snapshot_two"],
    }
    assert int(result["iceberg_snapshot_cherry_pick"]["current_snapshot_id"]) not in {
        result["iceberg_snapshot_one"],
        result["iceberg_snapshot_two"],
    }
    assert int(result["iceberg_snapshot_rewrite_data_files"]["rewritten_data_files_count"]) >= 2
    assert int(result["iceberg_snapshot_rewrite_data_files"]["added_data_files_count"]) >= 1
    assert int(result["iceberg_snapshot_rewrite_manifests"]["rewritten_manifests_count"]) >= 1
    assert sum(int(value or 0) for value in result["iceberg_snapshot_expire"].values()) >= 1
    assert result["iceberg_snapshot_orphan_dry_run"]
    assert result["iceberg_snapshot_orphan_removed"]
    assert all(
        str(value["orphan_file_location"]).endswith(result["iceberg_snapshot_orphan_key"])
        for value in (
            result["iceberg_snapshot_orphan_dry_run"] + result["iceberg_snapshot_orphan_removed"]
        )
    )
    assert result["iceberg_snapshot_orphan_exists_after_dry_run"] is True
    assert result["iceberg_snapshot_orphan_exists_after_remove"] is False


def _assert_iceberg_lifecycle_result(
    result: dict[str, Any],
    *,
    glue,
    s3,
    bucket: str,
) -> None:
    """Verify Glue pointers and S3 effects outside the Spark process.

    Source: https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416
    """
    assert result["iceberg_lifecycle_rename_keys_unchanged"] is True
    assert result["iceberg_lifecycle_renamed_rows"] == [{"id": 1, "payload": "rename"}]
    assert result["iceberg_lifecycle_collision_source_rows"] == []
    assert result["iceberg_lifecycle_collision_target_rows"] == []
    for error_key in (
        "iceberg_lifecycle_same_name_error",
        "iceberg_lifecycle_case_only_error",
        "iceberg_lifecycle_missing_namespace_error",
        "iceberg_lifecycle_collision_error",
        "iceberg_lifecycle_missing_source_error",
    ):
        assert result[error_key]

    target_database = result["iceberg_lifecycle_target_database"]
    target_table = glue.get_table(
        DatabaseName=target_database,
        Name=result["iceberg_lifecycle_renamed_table"],
    )["Table"]
    rename_uri = f"s3://{bucket}/{result['iceberg_lifecycle_rename_prefix']}"
    assert target_table["VersionId"] == "0"
    assert target_table["Parameters"]["table_type"].upper() == "ICEBERG"
    assert target_table["StorageDescriptor"]["Location"] == rename_uri
    assert target_table["Parameters"]["metadata_location"].startswith(f"{rename_uri}/metadata/")
    for missing_name in (
        result["iceberg_lifecycle_original_table"],
        result["iceberg_lifecycle_intermediate_table"],
    ):
        with pytest.raises(glue.exceptions.EntityNotFoundException):
            glue.get_table(DatabaseName=result["iceberg_database"], Name=missing_name)

    for collision_name in ("iceberg_collision_source", "iceberg_collision_target"):
        collision_table = glue.get_table(
            DatabaseName=result["iceberg_database"],
            Name=collision_name,
        )["Table"]
        assert collision_table["Parameters"]["table_type"].upper() == "ICEBERG"

    for deleted_name in (
        result["iceberg_lifecycle_drop_keep_table"],
        result["iceberg_lifecycle_drop_purge_table"],
    ):
        with pytest.raises(glue.exceptions.EntityNotFoundException):
            glue.get_table(DatabaseName=result["iceberg_database"], Name=deleted_name)

    kept_keys = _s3_keys(
        s3,
        bucket=bucket,
        prefix=result["iceberg_lifecycle_drop_keep_prefix"],
    )
    assert len(kept_keys) == result["iceberg_lifecycle_drop_keep_before_count"]
    assert len(kept_keys) == result["iceberg_lifecycle_drop_keep_after_count"]
    assert result["iceberg_lifecycle_drop_keep_sentinel"] in kept_keys
    assert len(kept_keys) > 1

    purged_keys = _s3_keys(
        s3,
        bucket=bucket,
        prefix=result["iceberg_lifecycle_drop_purge_prefix"],
    )
    assert result["iceberg_lifecycle_drop_purge_before_count"] > 1
    assert purged_keys == [result["iceberg_lifecycle_drop_purge_sentinel"]]
    s3.head_object(Bucket=bucket, Key=result["iceberg_lifecycle_unrelated_sentinel"])

    rename_keys = _s3_keys(
        s3,
        bucket=bucket,
        prefix=result["iceberg_lifecycle_rename_prefix"],
    )
    assert rename_keys


def _s3_keys(s3, *, bucket: str, prefix: str) -> list[str]:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return sorted(str(value["Key"]) for value in response.get("Contents", ()))


def _assert_iceberg_row_level_table(
    glue,
    s3,
    *,
    database: str,
    table: str,
    expected_mode: str,
    expected_version: int,
    expected_snapshots: int,
    expect_delete_files: bool,
) -> None:
    catalog_table = glue.get_table(DatabaseName=database, Name=table)["Table"]
    assert catalog_table["VersionId"] == str(expected_version)
    assert catalog_table["Parameters"]["table_type"].upper() == "ICEBERG"
    assert not catalog_table.get("PartitionKeys")
    metadata = IcebergMetadataDocument.load_from_s3(
        s3,
        catalog_table["Parameters"]["metadata_location"],
    )
    assert metadata.format_version() == 2
    assert metadata.snapshot_count() == expected_snapshots
    assert metadata.current_snapshot_id() > 0
    properties = metadata.properties()
    assert {properties[name] for name in _ROW_LEVEL_MODE_PROPERTIES} == {expected_mode}
    delete_file_count = int(metadata.current_snapshot_summary().get("total-delete-files", "0"))
    assert (delete_file_count > 0) is expect_delete_files


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
