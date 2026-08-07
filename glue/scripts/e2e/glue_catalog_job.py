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

from pyspark.sql import SparkSession


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
    iceberg_table = "iceberg_types"
    warehouse = f"s3://{args.bucket}/warehouse"
    builder = (
        SparkSession.builder.appName("mystack-glue-catalog-e2e")
        .config(
            "spark.hadoop.hive.metastore.client.factory.class",
            "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
        )
        .config("spark.hadoop.aws.glue.endpoint", args.catalog_endpoint)
        .config("spark.hadoop.aws.region", args.region)
        .config("spark.hadoop.hive.metastore.glue.catalogid", args.catalog_id)
        .config("spark.hadoop.fs.s3a.endpoint", args.object_store_endpoint)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            f"spark.sql.catalog.{args.catalog_name}",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config(
            f"spark.sql.catalog.{args.catalog_name}.catalog-impl",
            "org.apache.iceberg.aws.glue.GlueCatalog",
        )
        .config(
            f"spark.sql.catalog.{args.catalog_name}.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO",
        )
        .config(f"spark.sql.catalog.{args.catalog_name}.warehouse", warehouse)
        .config(
            f"spark.sql.catalog.{args.catalog_name}.glue.endpoint",
            args.catalog_endpoint,
        )
        .config(f"spark.sql.catalog.{args.catalog_name}.glue.id", args.catalog_id)
        .config(
            f"spark.sql.catalog.{args.catalog_name}.s3.endpoint",
            args.object_store_endpoint,
        )
        .config(f"spark.sql.catalog.{args.catalog_name}.s3.path-style-access", "true")
        .enableHiveSupport()
    )
    spark = builder.getOrCreate()
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
        print(
            "MYSTACK_E2E_RESULT="
            + json.dumps(
                {
                    "spark_version": spark.version,
                    "hive_database": hive_database,
                    "hive_count": hive_count,
                    "iceberg_database": iceberg_database,
                    "iceberg_count": iceberg_count,
                },
                sort_keys=True,
            )
        )
        if hive_count != 1 or iceberg_count != 2:
            raise RuntimeError("Unexpected catalog row counts")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
