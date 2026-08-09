"""Exercise Iceberg snapshot, reference, metadata-table, and procedure behavior.

Apache Iceberg owns every SQL and file operation in this module. Mystack is exercised only as
the GlueCatalog pointer store, while LocalStack supplies the S3-compatible object store.

Official references:
- https://iceberg.apache.org/docs/1.7.1/spark-queries/
- https://iceberg.apache.org/docs/1.7.1/spark-ddl/
- https://iceberg.apache.org/docs/1.7.1/spark-procedures/
- https://iceberg.apache.org/docs/1.7.1/branching/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from pyspark.sql import Row, SparkSession
from pyspark.sql.types import StringType, StructField, StructType, TimestampType


@dataclass(frozen=True, slots=True)
class IcebergSnapshotScenario:
    """Own one isolated, diagnosable real-Iceberg compatibility scenario."""

    spark: SparkSession
    catalog_name: str
    database: str
    bucket: str
    object_store_endpoint: str
    table: str = "iceberg_snapshot_refs"
    branch: str = "audit"
    tag: str = "historical"

    @property
    def qualified_table(self) -> str:
        return f"{self.catalog_name}.`{self.database}`.`{self.table}`"

    @property
    def procedure_table(self) -> str:
        return f"{self.database}.{self.table}"

    @property
    def table_location(self) -> str:
        return f"s3://{self.bucket}/iceberg/{self.database}/{self.table}"

    def run(self) -> dict[str, Any]:
        self._sql(
            "create-table",
            f"""
            CREATE TABLE {self.qualified_table} (
                id BIGINT,
                category STRING,
                payload STRING
            ) USING iceberg
            PARTITIONED BY (category)
            LOCATION '{self.table_location}'
            TBLPROPERTIES ('format-version'='2')
            """,
        )
        self._sql(
            "append-snapshot-one",
            f"INSERT INTO {self.qualified_table} VALUES (1, 'main', 'one')",
        )
        snapshot_one = self._current_snapshot()
        snapshot_one_time = self._snapshot_time(snapshot_one)

        self._sql(
            "append-snapshot-two",
            f"INSERT INTO {self.qualified_table} VALUES (2, 'main', 'two')",
        )
        snapshot_two = self._current_snapshot()

        version_rows = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table} VERSION AS OF {snapshot_one}"
        )
        timestamp_rows = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table} "
            f"TIMESTAMP AS OF '{self._timestamp_literal(snapshot_one_time)}'"
        )

        self._sql(
            "create-branch",
            f"ALTER TABLE {self.qualified_table} CREATE BRANCH {self.branch} "
            f"AS OF VERSION {snapshot_one}",
        )
        self._sql(
            "create-tag",
            f"ALTER TABLE {self.qualified_table} CREATE TAG {self.tag} "
            f"AS OF VERSION {snapshot_one}",
        )
        self._sql(
            "append-to-branch",
            f"INSERT INTO {self.qualified_table}.branch_{self.branch} VALUES (10, 'branch', 'ten')",
        )
        branch_snapshot = self._reference_snapshot(self.branch)
        main_before_cherry_pick = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table}"
        )
        branch_rows = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table} "
            f"VERSION AS OF '{self.branch}'"
        )
        tag_rows = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table} VERSION AS OF '{self.tag}'"
        )

        metadata_counts = {
            name: self.spark.sql(f"SELECT * FROM {self.qualified_table}.{name}").count()
            for name in ("history", "snapshots", "files", "manifests", "partitions")
        }

        rollback = self._procedure(
            "rollback-to-snapshot",
            "rollback_to_snapshot",
            f"table => '{self.procedure_table}', snapshot_id => {snapshot_one}",
        )
        rows_after_rollback = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table}"
        )
        set_current = self._procedure(
            "set-current-snapshot",
            "set_current_snapshot",
            f"table => '{self.procedure_table}', snapshot_id => {snapshot_two}",
        )
        cherry_pick = self._procedure(
            "cherry-pick-branch-append",
            "cherrypick_snapshot",
            f"table => '{self.procedure_table}', snapshot_id => {branch_snapshot}",
        )

        for row_id in (3, 4, 5):
            self._sql(
                f"append-small-file-{row_id}",
                f"INSERT INTO {self.qualified_table} VALUES ({row_id}, 'main', 'value-{row_id}')",
            )
        expected_rows = self._rows(f"SELECT id, category, payload FROM {self.qualified_table}")
        rewrite_data_files = self._procedure(
            "rewrite-data-files",
            "rewrite_data_files",
            f"table => '{self.procedure_table}', "
            "options => map('min-input-files','2','target-file-size-bytes','536870912')",
        )
        rewrite_manifests = self._procedure(
            "rewrite-manifests",
            "rewrite_manifests",
            f"table => '{self.procedure_table}', use_caching => false",
        )

        self._sql(
            "drop-branch",
            f"ALTER TABLE {self.qualified_table} DROP BRANCH {self.branch}",
        )
        self._sql(
            "drop-tag",
            f"ALTER TABLE {self.qualified_table} DROP TAG {self.tag}",
        )
        expire_snapshots = self._procedure(
            "expire-unreferenced-branch-snapshot",
            "expire_snapshots",
            f"table => '{self.procedure_table}', snapshot_ids => ARRAY({branch_snapshot})",
        )
        remaining_snapshot_ids = self._snapshot_ids()
        rows_after_maintenance = self._rows(
            f"SELECT id, category, payload FROM {self.qualified_table}"
        )
        orphan = self._exercise_orphan_cleanup()

        result = {
            "iceberg_snapshot_table": self.table,
            "iceberg_snapshot_one": snapshot_one,
            "iceberg_snapshot_two": snapshot_two,
            "iceberg_snapshot_branch": branch_snapshot,
            "iceberg_snapshot_version_rows": version_rows,
            "iceberg_snapshot_timestamp_rows": timestamp_rows,
            "iceberg_snapshot_main_before_cherry_pick": main_before_cherry_pick,
            "iceberg_snapshot_branch_rows": branch_rows,
            "iceberg_snapshot_tag_rows": tag_rows,
            "iceberg_snapshot_rows_after_rollback": rows_after_rollback,
            "iceberg_snapshot_final_rows": expected_rows,
            "iceberg_snapshot_rows_after_maintenance": rows_after_maintenance,
            "iceberg_snapshot_metadata_counts": metadata_counts,
            "iceberg_snapshot_rollback": rollback,
            "iceberg_snapshot_set_current": set_current,
            "iceberg_snapshot_cherry_pick": cherry_pick,
            "iceberg_snapshot_rewrite_data_files": rewrite_data_files,
            "iceberg_snapshot_rewrite_manifests": rewrite_manifests,
            "iceberg_snapshot_expire": expire_snapshots,
            "iceberg_snapshot_remaining_ids": remaining_snapshot_ids,
            **orphan,
        }
        self._log("scenario", "complete")
        return result

    def _exercise_orphan_cleanup(self) -> dict[str, Any]:
        orphan_key = f"iceberg/{self.database}/{self.table}/orphan/manual-orphan.bin"
        orphan_location = f"s3://{self.bucket}/{orphan_key}"
        s3 = boto3.client(
            "s3",
            endpoint_url=self.object_store_endpoint,
            config=Config(s3={"addressing_style": "path"}),
        )
        self._log("orphan-object", "before-create")
        s3.put_object(Bucket=self.bucket, Key=orphan_key, Body=b"mystack-orphan-contract")
        self._log("orphan-object", "after-create")

        schema = StructType(
            (
                StructField("file_path", StringType(), nullable=False),
                StructField("last_modified", TimestampType(), nullable=False),
            )
        )
        self.spark.createDataFrame(
            ((orphan_location, datetime(2000, 1, 1)),),
            schema=schema,
        ).createOrReplaceTempView("mystack_orphan_candidates")
        common_arguments = (
            f"table => '{self.procedure_table}', "
            "older_than => TIMESTAMP '2001-01-01 00:00:00', "
            "file_list_view => 'mystack_orphan_candidates'"
        )
        dry_run = self._procedure(
            "remove-orphan-dry-run",
            "remove_orphan_files",
            f"{common_arguments}, dry_run => true",
            multiple_rows=True,
        )
        exists_after_dry_run = self._object_exists(s3, orphan_key)
        removed = self._procedure(
            "remove-orphan",
            "remove_orphan_files",
            common_arguments,
            multiple_rows=True,
        )
        exists_after_remove = self._object_exists(s3, orphan_key)
        return {
            "iceberg_snapshot_orphan_key": orphan_key,
            "iceberg_snapshot_orphan_dry_run": dry_run,
            "iceberg_snapshot_orphan_removed": removed,
            "iceberg_snapshot_orphan_exists_after_dry_run": exists_after_dry_run,
            "iceberg_snapshot_orphan_exists_after_remove": exists_after_remove,
        }

    def _object_exists(self, s3: Any, key: str) -> bool:
        try:
            s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if str(error.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey"}:
                return False
            raise
        return True

    def _sql(self, name: str, statement: str) -> None:
        self._log(name, "before")
        try:
            self.spark.sql(statement).collect()
        except Exception as error:
            self._log(name, "error", error=error)
            raise
        self._log(name, "after")

    def _procedure(
        self,
        name: str,
        procedure: str,
        arguments: str,
        *,
        multiple_rows: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        self._log(name, "before")
        try:
            rows = self.spark.sql(
                f"CALL {self.catalog_name}.system.{procedure}({arguments})"
            ).collect()
        except Exception as error:
            self._log(name, "error", error=error)
            raise
        self._log(name, "after")
        values = [self._json_row(row) for row in rows]
        if multiple_rows:
            return values
        if len(values) != 1:
            raise RuntimeError(f"Procedure {procedure} returned {len(values)} rows; expected one")
        return values[0]

    def _current_snapshot(self) -> int:
        row = self._single_row(
            f"SELECT snapshot_id FROM {self.qualified_table}.history "
            "WHERE is_current_ancestor = true ORDER BY made_current_at DESC LIMIT 1"
        )
        return int(row.snapshot_id)

    def _snapshot_time(self, snapshot_id: int) -> datetime:
        row = self._single_row(
            f"SELECT committed_at FROM {self.qualified_table}.snapshots "
            f"WHERE snapshot_id = {snapshot_id}"
        )
        return row.committed_at

    def _reference_snapshot(self, name: str) -> int:
        row = self._single_row(
            f"SELECT snapshot_id FROM {self.qualified_table}.refs WHERE name = '{name}'"
        )
        return int(row.snapshot_id)

    def _single_row(self, statement: str) -> Row:
        rows = self.spark.sql(statement).collect()
        if len(rows) != 1:
            raise RuntimeError(f"Iceberg inspection returned {len(rows)} rows; expected one")
        return rows[0]

    def _snapshot_ids(self) -> list[int]:
        return sorted(
            int(row.snapshot_id)
            for row in self.spark.sql(
                f"SELECT snapshot_id FROM {self.qualified_table}.snapshots"
            ).collect()
        )

    def _rows(self, statement: str) -> list[dict[str, Any]]:
        return sorted(
            (self._json_row(row) for row in self.spark.sql(statement).collect()),
            key=lambda value: (int(value["id"]), str(value.get("category", ""))),
        )

    @staticmethod
    def _timestamp_literal(value: datetime) -> str:
        return value.isoformat(sep=" ", timespec="milliseconds")

    @staticmethod
    def _json_row(row: Row) -> dict[str, Any]:
        return {
            key: IcebergSnapshotScenario._json_value(value) for key, value in row.asDict().items()
        }

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): IcebergSnapshotScenario._json_value(item) for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [IcebergSnapshotScenario._json_value(item) for item in value]
        return value

    @staticmethod
    def _log(name: str, phase: str, *, error: Exception | None = None) -> None:
        event = {"name": name, "phase": phase}
        if error is not None:
            event["error_type"] = type(error).__name__
        print("MYSTACK_E2E_SCENARIO=" + json.dumps(event, sort_keys=True), flush=True)


def exercise_iceberg_snapshots_and_procedures(
    spark: SparkSession,
    *,
    catalog_name: str,
    database: str,
    bucket: str,
    object_store_endpoint: str,
) -> dict[str, Any]:
    """Run the public entry point used by the Glue catalog E2E job."""

    return IcebergSnapshotScenario(
        spark=spark,
        catalog_name=catalog_name,
        database=database,
        bucket=bucket,
        object_store_endpoint=object_store_endpoint,
    ).run()
