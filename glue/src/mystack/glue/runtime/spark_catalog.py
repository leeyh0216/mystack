"""Reusable Spark Hive/Iceberg Catalog client configuration.

The component owns the client-side configuration shared by local interoperability workloads. It
does not perform Glue I/O until ``create_session`` is called, so callers can inspect or test the
immutable option set without importing PySpark.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlueSparkCatalogSettings:
    """Endpoint and identity facts for one Spark Hive plus Iceberg client session."""

    catalog_endpoint: str
    object_store_endpoint: str
    region: str
    catalog_id: str
    bucket: str
    catalog_name: str

    def options(self) -> tuple[tuple[str, str], ...]:
        """Return the complete deterministic Spark option set without constructing a session."""

        warehouse = f"s3://{self.bucket}/warehouse"
        return (
            (
                "spark.hadoop.hive.metastore.client.factory.class",
                "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
            ),
            ("spark.hadoop.aws.glue.endpoint", self.catalog_endpoint),
            ("spark.hadoop.aws.region", self.region),
            ("spark.hadoop.hive.metastore.glue.catalogid", self.catalog_id),
            ("spark.hadoop.fs.s3a.endpoint", self.object_store_endpoint),
            ("spark.hadoop.fs.s3a.path.style.access", "true"),
            ("spark.hadoop.fs.s3a.connection.ssl.enabled", "false"),
            (
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            ),
            (f"spark.sql.catalog.{self.catalog_name}", "org.apache.iceberg.spark.SparkCatalog"),
            (
                f"spark.sql.catalog.{self.catalog_name}.catalog-impl",
                "org.apache.iceberg.aws.glue.GlueCatalog",
            ),
            (
                f"spark.sql.catalog.{self.catalog_name}.io-impl",
                "org.apache.iceberg.aws.s3.S3FileIO",
            ),
            (f"spark.sql.catalog.{self.catalog_name}.warehouse", warehouse),
            (f"spark.sql.catalog.{self.catalog_name}.glue.endpoint", self.catalog_endpoint),
            (f"spark.sql.catalog.{self.catalog_name}.glue.id", self.catalog_id),
            (f"spark.sql.catalog.{self.catalog_name}.s3.endpoint", self.object_store_endpoint),
            (f"spark.sql.catalog.{self.catalog_name}.s3.path-style-access", "true"),
        )

    def create_session(self, app_name: str):
        """Construct one real Spark session only in a Spark-capable client runtime."""

        from pyspark.sql import SparkSession

        builder = SparkSession.builder.appName(app_name)
        for key, value in self.options():
            builder = builder.config(key, value)
        return builder.enableHiveSupport().getOrCreate()
