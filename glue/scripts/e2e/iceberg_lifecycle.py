"""Exercise Iceberg 1.7.1 GlueCatalog rename, drop, and purge behavior.

Apache Iceberg owns the multi-call rename choreography and tracked-file deletion. Mystack provides
the individual modeled Glue operations; LocalStack provides the configured S3 endpoint.

Official references:
- https://iceberg.apache.org/docs/1.7.1/spark-ddl/
- https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config
from pyspark.sql import SparkSession


@dataclass(frozen=True, slots=True)
class IcebergLifecycleScenario:
    """Own one isolated lifecycle scenario and its object-store evidence."""

    spark: SparkSession
    catalog_name: str
    database: str
    bucket: str
    object_store_endpoint: str

    @property
    def target_database(self) -> str:
        return f"{self.database}_lifecycle_target"

    def run(self) -> dict[str, Any]:
        self._sql(
            "create-lifecycle-target-namespace",
            f"CREATE NAMESPACE IF NOT EXISTS {self.catalog_name}.`{self.target_database}`",
        )
        rename = self._exercise_rename()
        drop = self._exercise_drop_and_purge()
        self._emit("lifecycle-scenario", "complete")
        return {**rename, **drop}

    def _exercise_rename(self) -> dict[str, Any]:
        source = "iceberg_rename_source"
        renamed = "iceberg_renamed"
        cross_database = "iceberg_cross_renamed"
        prefix = f"iceberg/{self.database}/lifecycle/rename"
        source_qualified = self._qualified(self.database, source)
        renamed_qualified = self._qualified(self.database, renamed)
        cross_qualified = self._qualified(self.target_database, cross_database)
        self._create_table(source_qualified, prefix)
        self._sql(
            "insert-rename-source",
            f"INSERT INTO {source_qualified} VALUES (1, 'rename')",
        )
        keys_before = self._keys(prefix)
        self._sql(
            "rename-within-namespace",
            f"ALTER TABLE {source_qualified} RENAME TO "
            f"{self._rename_target(self.database, renamed)}",
        )
        same_name_error = self._expect_failure(
            "rename-same-name",
            f"ALTER TABLE {renamed_qualified} RENAME TO "
            f"{self._rename_target(self.database, renamed)}",
        )
        case_only_error = self._expect_failure(
            "rename-case-only",
            f"ALTER TABLE {renamed_qualified} RENAME TO "
            f"{self._rename_target(self.database, 'ICEBERG_RENAMED')}",
        )
        missing_namespace_error = self._expect_failure(
            "rename-missing-namespace",
            f"ALTER TABLE {renamed_qualified} RENAME TO "
            f"{self._rename_target(f'{self.database}_missing', 'unreachable')}",
        )

        collision_source = self._qualified(self.database, "iceberg_collision_source")
        collision_target = self._qualified(self.database, "iceberg_collision_target")
        self._create_table(
            collision_source,
            f"iceberg/{self.database}/lifecycle/collision-source",
        )
        self._create_table(
            collision_target,
            f"iceberg/{self.database}/lifecycle/collision-target",
        )
        collision_error = self._expect_failure(
            "rename-existing-target",
            f"ALTER TABLE {collision_source} RENAME TO "
            f"{self._rename_target(self.database, 'iceberg_collision_target')}",
        )
        missing_source_error = self._expect_failure(
            "rename-missing-source",
            f"ALTER TABLE {self._qualified(self.database, 'iceberg_missing_source')} "
            f"RENAME TO {self._rename_target(self.database, 'iceberg_missing_target')}",
        )

        self._sql(
            "rename-across-namespace",
            f"ALTER TABLE {renamed_qualified} RENAME TO "
            f"{self._rename_target(self.target_database, cross_database)}",
        )
        keys_after = self._keys(prefix)
        return {
            "iceberg_lifecycle_target_database": self.target_database,
            "iceberg_lifecycle_renamed_table": cross_database,
            "iceberg_lifecycle_original_table": source,
            "iceberg_lifecycle_intermediate_table": renamed,
            "iceberg_lifecycle_rename_prefix": prefix,
            "iceberg_lifecycle_rename_keys_unchanged": keys_before == keys_after,
            "iceberg_lifecycle_renamed_rows": self._rows(cross_qualified),
            "iceberg_lifecycle_same_name_error": same_name_error,
            "iceberg_lifecycle_case_only_error": case_only_error,
            "iceberg_lifecycle_missing_namespace_error": missing_namespace_error,
            "iceberg_lifecycle_collision_error": collision_error,
            "iceberg_lifecycle_missing_source_error": missing_source_error,
            "iceberg_lifecycle_collision_source_rows": self._rows(collision_source),
            "iceberg_lifecycle_collision_target_rows": self._rows(collision_target),
        }

    def _exercise_drop_and_purge(self) -> dict[str, Any]:
        nonpurge = "iceberg_drop_keep"
        purge = "iceberg_drop_purge"
        nonpurge_prefix = f"iceberg/{self.database}/lifecycle/drop-keep"
        purge_prefix = f"iceberg/{self.database}/lifecycle/drop-purge"
        unrelated_key = f"iceberg/{self.database}/lifecycle/unrelated/sentinel.bin"
        nonpurge_sentinel = f"{nonpurge_prefix}/untracked-sentinel.bin"
        purge_sentinel = f"{purge_prefix}/untracked-sentinel.bin"
        nonpurge_qualified = self._qualified(self.database, nonpurge)
        purge_qualified = self._qualified(self.database, purge)
        self._create_table(nonpurge_qualified, nonpurge_prefix)
        self._create_table(purge_qualified, purge_prefix)
        self._sql(
            "insert-drop-keep",
            f"INSERT INTO {nonpurge_qualified} VALUES (20, 'keep')",
        )
        self._sql(
            "insert-drop-purge-one",
            f"INSERT INTO {purge_qualified} VALUES (30, 'purge-one')",
        )
        self._sql(
            "insert-drop-purge-two",
            f"INSERT INTO {purge_qualified} VALUES (31, 'purge-two')",
        )
        s3 = self._s3()
        for name, key in (
            ("drop-keep-sentinel", nonpurge_sentinel),
            ("drop-purge-sentinel", purge_sentinel),
            ("unrelated-sentinel", unrelated_key),
        ):
            self._emit(name, "before")
            s3.put_object(Bucket=self.bucket, Key=key, Body=b"mystack-lifecycle-sentinel")
            self._emit(name, "after")

        nonpurge_before = self._keys(nonpurge_prefix)
        purge_before = self._keys(purge_prefix)
        self._sql("drop-without-purge", f"DROP TABLE {nonpurge_qualified}")
        self._sql(
            "drop-without-purge-idempotent-retry",
            f"DROP TABLE IF EXISTS {nonpurge_qualified}",
        )
        nonpurge_after = self._keys(nonpurge_prefix)
        self._sql("drop-with-purge", f"DROP TABLE {purge_qualified} PURGE")
        self._sql(
            "drop-with-purge-idempotent-retry",
            f"DROP TABLE IF EXISTS {purge_qualified} PURGE",
        )
        purge_after = self._keys(purge_prefix)
        return {
            "iceberg_lifecycle_drop_keep_table": nonpurge,
            "iceberg_lifecycle_drop_purge_table": purge,
            "iceberg_lifecycle_drop_keep_prefix": nonpurge_prefix,
            "iceberg_lifecycle_drop_purge_prefix": purge_prefix,
            "iceberg_lifecycle_drop_keep_sentinel": nonpurge_sentinel,
            "iceberg_lifecycle_drop_purge_sentinel": purge_sentinel,
            "iceberg_lifecycle_unrelated_sentinel": unrelated_key,
            "iceberg_lifecycle_drop_keep_before_count": len(nonpurge_before),
            "iceberg_lifecycle_drop_keep_after_count": len(nonpurge_after),
            "iceberg_lifecycle_drop_keep_objects_unchanged": (nonpurge_before == nonpurge_after),
            "iceberg_lifecycle_drop_purge_before_count": len(purge_before),
            "iceberg_lifecycle_drop_purge_after_keys": purge_after,
            "iceberg_lifecycle_unrelated_sentinel_exists": unrelated_key
            in self._keys(unrelated_key),
        }

    def _qualified(self, database: str, table: str) -> str:
        return f"{self.catalog_name}.`{database}`.`{table}`"

    @staticmethod
    def _rename_target(database: str, table: str) -> str:
        """Keep the target relative to the source catalog.

        Spark resolves the source catalog first. Repeating it in the target is interpreted as a
        namespace segment by Iceberg's RenameTableExec path.

        Source: https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html
        """

        return f"`{database}`.`{table}`"

    def _create_table(self, qualified: str, prefix: str) -> None:
        self._sql(
            f"create-{qualified.rsplit('.', maxsplit=1)[-1].strip('`')}",
            f"""
            CREATE TABLE {qualified} (id BIGINT, payload STRING)
            USING iceberg
            LOCATION 's3://{self.bucket}/{prefix}'
            TBLPROPERTIES ('format-version'='2')
            """,
        )

    def _rows(self, qualified: str) -> list[dict[str, Any]]:
        return [
            {"id": int(row.id), "payload": str(row.payload)}
            for row in self.spark.sql(f"SELECT id, payload FROM {qualified} ORDER BY id").collect()
        ]

    def _sql(self, name: str, statement: str) -> None:
        self._emit(name, "before")
        try:
            self.spark.sql(statement).collect()
        except Exception as error:
            self._emit(name, "error", error_type=type(error).__name__)
            raise
        self._emit(name, "after")

    def _expect_failure(self, name: str, statement: str) -> str:
        self._emit(name, "before")
        try:
            self.spark.sql(statement).collect()
        except Exception as error:
            error_name = type(error).__name__
            self._emit(name, "expected-failure", error_type=error_name)
            return error_name
        raise RuntimeError(f"Expected lifecycle scenario {name!r} to fail")

    def _keys(self, prefix: str) -> list[str]:
        response = self._s3().list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return sorted(str(value["Key"]) for value in response.get("Contents", ()))

    def _s3(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=self.object_store_endpoint,
            config=Config(s3={"addressing_style": "path"}),
        )

    @staticmethod
    def _emit(name: str, phase: str, **fields: str) -> None:
        print(
            "MYSTACK_E2E_SCENARIO="
            + json.dumps({"name": name, "phase": phase, **fields}, sort_keys=True),
            flush=True,
        )


def exercise_iceberg_lifecycle(
    spark: SparkSession,
    *,
    catalog_name: str,
    database: str,
    bucket: str,
    object_store_endpoint: str,
) -> dict[str, Any]:
    """Run the public entry point used by the Glue catalog E2E job."""

    return IcebergLifecycleScenario(
        spark=spark,
        catalog_name=catalog_name,
        database=database,
        bucket=bucket,
        object_store_endpoint=object_store_endpoint,
    ).run()
