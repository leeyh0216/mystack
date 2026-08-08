"""Real Glue 5 Spark, Hive metastore, and Iceberg catalog interoperability check.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore
- https://iceberg.apache.org/docs/1.7.1/aws/
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from iceberg_evolution import exercise_iceberg_evolution
from iceberg_row_level import exercise_iceberg_row_level_writes
from pyspark.sql import SparkSession
from spark_catalog_session import GlueSparkCatalogSettings


@dataclass(frozen=True, slots=True)
class SqlScenario:
    """One diagnosable Spark SQL boundary derived from the official DDL syntax."""

    name: str
    statement: str


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-endpoint", required=True)
    parser.add_argument("--object-store-endpoint", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--catalog-name", required=True)
    args = parser.parse_args()

    hive_database = f"{args.database}_hive"
    iceberg_database = f"{args.database}_iceberg"
    hive_table = "hive_types"
    hive_partition_table = "hive_partition_pruning"
    hive_ddl_table = "hive_partition_ddl"
    hive_repair_table = "hive_partition_repair"
    hive_alter_table = "hive_table_alter"
    iceberg_table = "iceberg_types"
    spark = GlueSparkCatalogSettings(
        catalog_endpoint=args.catalog_endpoint,
        object_store_endpoint=args.object_store_endpoint,
        region=args.region,
        catalog_id=args.catalog_id,
        bucket=args.bucket,
        catalog_name=args.catalog_name,
    ).create_session("mystack-glue-catalog-e2e")
    try:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS `{hive_database}`")
        spark.sql(
            f"""
            CREATE TABLE `{hive_database}`.`{hive_table}` (
                id BIGINT,
                amount DECIMAL(18, 4),
                labels ARRAY<STRING>,
                attributes MAP<STRING, STRING>,
                payload STRUCT<enabled:BOOLEAN, observed_at:TIMESTAMP>
            ) USING PARQUET
            LOCATION 's3a://{args.bucket}/hive/{hive_table}'
            """
        )
        spark.sql(
            f"""
            INSERT INTO `{hive_database}`.`{hive_table}`
            SELECT 1, CAST(12.3400 AS DECIMAL(18, 4)), ARRAY('a', 'b'),
                   MAP('source', 'mystack'),
                   NAMED_STRUCT(
                     'enabled', true,
                     'observed_at', TIMESTAMP'2026-01-01 00:00:00'
                   )
            """
        )
        hive_count = spark.table(f"`{hive_database}`.`{hive_table}`").count()
        spark.sql(
            f"""
            CREATE TABLE `{hive_database}`.`{hive_partition_table}` (
                id BIGINT,
                event_date DATE,
                region STRING
            ) USING PARQUET
            PARTITIONED BY (event_date, region)
            LOCATION 's3a://{args.bucket}/hive/{hive_partition_table}'
            """
        )
        spark.sql(
            f"""
            INSERT INTO `{hive_database}`.`{hive_partition_table}` VALUES
              (1, DATE'2026-08-08', 'ap-northeast-2'),
              (2, DATE'2026-08-09', 'ap-southeast-1'),
              (3, DATE'2025-01-01', 'us-east-1')
            """
        )
        hive_pruned_count = spark.sql(
            f"""
            SELECT * FROM `{hive_database}`.`{hive_partition_table}`
            WHERE event_date BETWEEN DATE'2026-08-08' AND DATE'2026-08-31'
              AND region LIKE 'ap-%'
            """
        ).count()
        hive_ddl_partitions = _exercise_hive_partition_ddl(
            spark,
            database=hive_database,
            table=hive_ddl_table,
            bucket=args.bucket,
        )
        hive_repair_partitions = _exercise_hive_partition_repair(
            spark,
            database=hive_database,
            table=hive_repair_table,
            bucket=args.bucket,
        )
        hive_alter_failures = _exercise_hive_table_alter(
            spark,
            database=hive_database,
            table=hive_alter_table,
            bucket=args.bucket,
        )

        qualified_namespace = f"{args.catalog_name}.`{iceberg_database}`"
        qualified_table = f"{qualified_namespace}.`{iceberg_table}`"
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {qualified_namespace}")
        spark.sql(
            f"""
            CREATE TABLE {qualified_table} (
                id BIGINT,
                event_date DATE,
                attributes MAP<STRING, STRING>
            ) USING iceberg
            TBLPROPERTIES ('format-version'='2')
            """
        )
        spark.sql(
            f"""
            INSERT INTO {qualified_table} VALUES
              (1, DATE'2026-01-01', MAP('kind', 'created')),
              (2, DATE'2026-01-02', MAP('kind', 'updated'))
            """
        )
        spark.sql(f"ALTER TABLE {qualified_table} ADD COLUMN note STRING")
        iceberg_count = spark.table(qualified_table).count()
        iceberg_evolution = exercise_iceberg_evolution(
            spark,
            catalog_name=args.catalog_name,
            database=iceberg_database,
        )
        iceberg_row_level = exercise_iceberg_row_level_writes(
            spark,
            catalog_name=args.catalog_name,
            database=iceberg_database,
        )
        print(
            "MYSTACK_E2E_RESULT="
            + json.dumps(
                {
                    "spark_version": spark.version,
                    "hive_database": hive_database,
                    "hive_count": hive_count,
                    "hive_pruned_count": hive_pruned_count,
                    "hive_ddl_table": hive_ddl_table,
                    "hive_ddl_partitions": sorted(hive_ddl_partitions),
                    "hive_repair_table": hive_repair_table,
                    "hive_repair_partitions": sorted(hive_repair_partitions),
                    "hive_alter_table": hive_alter_table,
                    "hive_alter_failures": hive_alter_failures,
                    "iceberg_database": iceberg_database,
                    "iceberg_count": iceberg_count,
                    **iceberg_evolution,
                    **iceberg_row_level,
                },
                sort_keys=True,
            )
        )
        if (
            hive_count != 1
            or hive_pruned_count != 2
            or len(hive_ddl_partitions) != 2
            or len(hive_repair_partitions) != 2
            or set(hive_alter_failures)
            != {"drop-column", "rename-column", "change-column-type", "rename-table"}
            or iceberg_count != 2
            or iceberg_evolution["iceberg_evolution_count"] != 2
            or iceberg_evolution["iceberg_evolution_filtered_count"] != 1
            or iceberg_row_level["iceberg_row_cow_after_overwrite"]
            != [
                {"id": 1, "category": "north", "amount": 11},
                {"id": 3, "category": "south", "amount": 30},
                {"id": 4, "category": "south", "amount": 40},
                {"id": 5, "category": "north", "amount": 50},
            ]
            or iceberg_row_level["iceberg_row_cow_final"]
            != [
                {"id": 1, "category": "north", "amount": 111},
                {"id": 3, "category": "south", "amount": 31},
                {"id": 6, "category": "south", "amount": 60},
            ]
            or iceberg_row_level["iceberg_row_mor_final"]
            != [
                {"id": 10, "category": "north", "amount": 101},
                {"id": 12, "category": "south", "amount": 121},
                {"id": 13, "category": "south", "amount": 130},
            ]
            or not iceberg_row_level["iceberg_row_cow_invalid_merge_error"]
        ):
            raise RuntimeError("Unexpected Glue Spark catalog E2E result")
    finally:
        spark.stop()


def _exercise_hive_partition_ddl(
    spark: SparkSession,
    *,
    database: str,
    table: str,
    bucket: str,
) -> set[str]:
    """Run Spark 3.5 ALTER PARTITION forms through the Glue Hive client.

    Source: https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html
    """
    qualified = f"`{database}`.`{table}`"
    base = f"s3a://{bucket}/hive/{table}"
    preserved_drop_path = f"{base}/drop-preserved"
    spark.range(1).write.mode("overwrite").parquet(preserved_drop_path)
    _run_scenarios(
        spark,
        (
            SqlScenario(
                "create-ddl-table",
                f"""
                CREATE TABLE {qualified} (id BIGINT, day DATE, region STRING)
                USING PARQUET PARTITIONED BY (day, region) LOCATION '{base}/table'
                """,
            ),
            SqlScenario(
                "add-single-complex-value",
                f"""
                ALTER TABLE {qualified} ADD
                PARTITION (day=DATE'2026-08-01', region='ap/northeast=2')
                LOCATION '{base}/complex'
                """,
            ),
            SqlScenario(
                "add-if-not-exists",
                f"""
                ALTER TABLE {qualified} ADD IF NOT EXISTS
                PARTITION (day=DATE'2026-08-01', region='ap/northeast=2')
                LOCATION '{base}/ignored-duplicate'
                """,
            ),
            SqlScenario(
                "add-multiple",
                f"""
                ALTER TABLE {qualified} ADD IF NOT EXISTS
                PARTITION (day=DATE'2026-08-02', region='west') LOCATION '{base}/rename-source'
                PARTITION (day=DATE'2026-08-03', region='drop') LOCATION '{preserved_drop_path}'
                """,
            ),
            SqlScenario(
                "rename-partition",
                f"""
                ALTER TABLE {qualified}
                PARTITION (day=DATE'2026-08-02', region='west')
                RENAME TO PARTITION (day=DATE'2026-08-20', region='west')
                """,
            ),
            SqlScenario(
                "set-partition-location",
                f"""
                ALTER TABLE {qualified}
                PARTITION (day=DATE'2026-08-20', region='west')
                SET LOCATION '{base}/location-updated'
                """,
            ),
            SqlScenario(
                "drop-partition",
                f"""
                ALTER TABLE {qualified} DROP
                PARTITION (day=DATE'2026-08-03', region='drop')
                """,
            ),
            SqlScenario(
                "drop-if-exists",
                f"""
                ALTER TABLE {qualified} DROP IF EXISTS
                PARTITION (day=DATE'1900-01-01', region='missing')
                """,
            ),
        ),
    )
    return _show_partitions(spark, qualified)


def _exercise_hive_partition_repair(
    spark: SparkSession,
    *,
    database: str,
    table: str,
    bucket: str,
) -> set[str]:
    """Cover default/ADD/DROP/SYNC repair plus ALTER RECOVER PARTITIONS.

    Source: https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-repair-table.html
    """
    qualified = f"`{database}`.`{table}`"
    location = f"s3a://{bucket}/hive/{table}"
    _write_physical_partition(spark, location, 1, "2026-09-01", "north", "overwrite")
    _run_scenarios(
        spark,
        (
            SqlScenario(
                "create-repair-table",
                f"""
                CREATE TABLE {qualified} (id BIGINT, day STRING, region STRING)
                USING PARQUET PARTITIONED BY (day, region) LOCATION '{location}'
                """,
            ),
            SqlScenario("repair-default-add", f"MSCK REPAIR TABLE {qualified}"),
        ),
    )
    _write_physical_partition(spark, location, 2, "2026-09-02", "south", "append")
    _run_scenarios(
        spark,
        (SqlScenario("repair-explicit-add", f"MSCK REPAIR TABLE {qualified} ADD PARTITIONS"),),
    )
    _write_physical_partition(spark, location, 3, "2026-09-03", "west", "append")
    _run_scenarios(
        spark,
        (SqlScenario("alter-recover", f"ALTER TABLE {qualified} RECOVER PARTITIONS"),),
    )
    _delete_physical_partition(spark, location, "2026-09-01", "north")
    _run_scenarios(
        spark,
        (SqlScenario("repair-drop", f"MSCK REPAIR TABLE {qualified} DROP PARTITIONS"),),
    )
    _write_physical_partition(spark, location, 4, "2026-09-04", "east", "append")
    _delete_physical_partition(spark, location, "2026-09-02", "south")
    _run_scenarios(
        spark,
        (SqlScenario("repair-sync", f"MSCK REPAIR TABLE {qualified} SYNC PARTITIONS"),),
    )
    return _show_partitions(spark, qualified)


def _exercise_hive_table_alter(
    spark: SparkSession,
    *,
    database: str,
    table: str,
    bucket: str,
) -> dict[str, str]:
    """Exercise table-level Hive V1 ALTER boundaries without inventing SQL semantics.

    Spark documents DROP/RENAME COLUMN and REPLACE COLUMNS as V2-only. Its V1 command permits
    column-comment changes but rejects column name and type changes. The official Glue Hive client
    rejects table rename before calling UpdateTable.

    Sources:
    - https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html
    - https://github.com/apache/spark/blob/v3.5.4/sql/core/src/main/scala/org/apache/spark/sql/execution/command/ddl.scala
    - https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/branch-3.4.0/aws-glue-datacatalog-client-common/src/main/java/com/amazonaws/glue/catalog/metastore/GlueMetastoreClientDelegate.java
    """
    qualified = f"`{database}`.`{table}`"
    base = f"s3a://{bucket}/hive/{table}"
    _run_scenarios(
        spark,
        (
            SqlScenario(
                "create-hive-alter-table",
                f"""
                CREATE EXTERNAL TABLE {qualified} (
                    id INT,
                    payload STRUCT<kind:STRING,tags:ARRAY<STRING>>
                ) PARTITIONED BY (day STRING)
                STORED AS PARQUET
                LOCATION '{base}/original'
                TBLPROPERTIES (
                    'mystack.contract.keep'='before',
                    'mystack.contract.remove'='remove-me'
                )
                """,
            ),
            SqlScenario(
                "add-hive-alter-partition",
                f"""
                ALTER TABLE {qualified} ADD PARTITION (day='2026-08-09')
                LOCATION '{base}/partition'
                """,
            ),
            SqlScenario(
                "add-complex-column",
                f"""
                ALTER TABLE {qualified} ADD COLUMNS (
                    note ARRAY<STRUCT<source:STRING,weight:DECIMAL(10,2)>> COMMENT 'added'
                )
                """,
            ),
            SqlScenario(
                "change-column-comment",
                f"ALTER TABLE {qualified} ALTER COLUMN payload COMMENT 'payload comment'",
            ),
            SqlScenario(
                "set-table-properties",
                f"""
                ALTER TABLE {qualified} SET TBLPROPERTIES (
                    'mystack.contract.keep'='after',
                    'mystack.contract.added'='true'
                )
                """,
            ),
            SqlScenario(
                "unset-table-properties",
                f"""
                ALTER TABLE {qualified} UNSET TBLPROPERTIES (
                    'mystack.contract.remove'
                )
                """,
            ),
            SqlScenario(
                "set-serde-properties",
                f"""
                ALTER TABLE {qualified} SET SERDEPROPERTIES (
                    'serialization.format'='1',
                    'mystack.contract.serde'='true'
                )
                """,
            ),
            SqlScenario(
                "set-table-location",
                f"ALTER TABLE {qualified} SET LOCATION '{base}/relocated'",
            ),
        ),
    )
    return {
        name: _expect_sql_failure(spark, name, statement)
        for name, statement in (
            ("drop-column", f"ALTER TABLE {qualified} DROP COLUMN payload"),
            (
                "rename-column",
                f"ALTER TABLE {qualified} RENAME COLUMN payload TO renamed_payload",
            ),
            (
                "change-column-type",
                f"ALTER TABLE {qualified} CHANGE COLUMN id id BIGINT",
            ),
            (
                "rename-table",
                f"ALTER TABLE {qualified} RENAME TO `{database}`.`{table}_renamed`",
            ),
        )
    }


def _run_scenarios(spark: SparkSession, scenarios: tuple[SqlScenario, ...]) -> None:
    for scenario in scenarios:
        print("MYSTACK_E2E_SCENARIO=" + json.dumps({"name": scenario.name, "phase": "before"}))
        spark.sql(scenario.statement).collect()
        print("MYSTACK_E2E_SCENARIO=" + json.dumps({"name": scenario.name, "phase": "after"}))


def _expect_sql_failure(spark: SparkSession, name: str, statement: str) -> str:
    print("MYSTACK_E2E_SCENARIO=" + json.dumps({"name": name, "phase": "before"}))
    try:
        spark.sql(statement).collect()
    except Exception as error:
        error_name = type(error).__name__
        print(
            "MYSTACK_E2E_SCENARIO="
            + json.dumps(
                {"name": name, "phase": "expected-failure", "error_type": error_name},
                sort_keys=True,
            )
        )
        return error_name
    raise RuntimeError(f"Expected Spark SQL scenario {name!r} to fail")


def _write_physical_partition(
    spark: SparkSession,
    location: str,
    identifier: int,
    day: str,
    region: str,
    mode: str,
) -> None:
    frame = spark.createDataFrame(
        [(identifier, day, region)],
        "id long, day string, region string",
    )
    frame.write.mode(mode).partitionBy("day", "region").parquet(location)


def _delete_physical_partition(
    spark: SparkSession,
    location: str,
    day: str,
    region: str,
) -> None:
    path = spark._jvm.org.apache.hadoop.fs.Path(f"{location}/day={day}/region={region}")
    filesystem = path.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration())
    if not filesystem.delete(path, True):
        raise RuntimeError(f"Physical partition path was not deleted: day={day}, region={region}")


def _show_partitions(spark: SparkSession, qualified_table: str) -> set[str]:
    return {str(row[0]) for row in spark.sql(f"SHOW PARTITIONS {qualified_table}").collect()}


if __name__ == "__main__":
    main()
