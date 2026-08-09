"""Run a minimal Spark Hive and Iceberg client round trip through Mystack."""

from __future__ import annotations

from mystack.glue.runtime.spark_catalog import GlueSparkCatalogSettings


def main() -> None:
    catalog_name = "mystack"
    database = "client_lab"
    bucket = "mystack-spark-client-lab"
    hive_database = f"{database}_hive"
    iceberg_database = f"{database}_iceberg"
    spark = GlueSparkCatalogSettings(
        catalog_endpoint="http://proxy:8080",
        object_store_endpoint="http://localstack:4566",
        region="us-east-1",
        catalog_id="000000000000",
        bucket=bucket,
        catalog_name=catalog_name,
    ).create_session("mystack-spark-client-lab")
    try:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS `{hive_database}`")
        spark.sql(
            f"""
            CREATE TABLE `{hive_database}`.`events` (id BIGINT, source STRING)
            USING PARQUET
            LOCATION 's3a://{bucket}/hive/events'
            """
        )
        spark.sql(f"INSERT INTO `{hive_database}`.`events` VALUES (1, 'spark-client')")
        hive_count = spark.table(f"`{hive_database}`.`events`").count()

        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog_name}.`{iceberg_database}`")
        iceberg_table = f"{catalog_name}.`{iceberg_database}`.`events`"
        spark.sql(
            f"""
            CREATE TABLE {iceberg_table} (id BIGINT, source STRING)
            USING iceberg
            LOCATION 's3://{bucket}/iceberg/events'
            """
        )
        spark.sql(f"INSERT INTO {iceberg_table} VALUES (1, 'spark-client')")
        iceberg_count = spark.table(iceberg_table).count()
        print(
            {
                "hive_database": hive_database,
                "hive_count": hive_count,
                "iceberg_database": iceberg_database,
                "iceberg_count": iceberg_count,
            }
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
