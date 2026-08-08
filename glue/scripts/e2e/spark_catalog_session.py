"""Shared real Glue 5 Spark session assembly for catalog E2E jobs.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://iceberg.apache.org/docs/1.7.1/aws/
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import SparkSession


@dataclass(frozen=True, slots=True)
class GlueSparkCatalogSettings:
    catalog_endpoint: str
    object_store_endpoint: str
    region: str
    catalog_id: str
    bucket: str
    catalog_name: str

    def create_session(self, app_name: str) -> SparkSession:
        warehouse = f"s3://{self.bucket}/warehouse"
        return (
            SparkSession.builder.appName(app_name)
            .config(
                "spark.hadoop.hive.metastore.client.factory.class",
                "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
            )
            .config("spark.hadoop.aws.glue.endpoint", self.catalog_endpoint)
            .config("spark.hadoop.aws.region", self.region)
            .config("spark.hadoop.hive.metastore.glue.catalogid", self.catalog_id)
            .config("spark.hadoop.fs.s3a.endpoint", self.object_store_endpoint)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
            .config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
            .config(
                f"spark.sql.catalog.{self.catalog_name}",
                "org.apache.iceberg.spark.SparkCatalog",
            )
            .config(
                f"spark.sql.catalog.{self.catalog_name}.catalog-impl",
                "org.apache.iceberg.aws.glue.GlueCatalog",
            )
            .config(
                f"spark.sql.catalog.{self.catalog_name}.io-impl",
                "org.apache.iceberg.aws.s3.S3FileIO",
            )
            .config(f"spark.sql.catalog.{self.catalog_name}.warehouse", warehouse)
            .config(
                f"spark.sql.catalog.{self.catalog_name}.glue.endpoint",
                self.catalog_endpoint,
            )
            .config(f"spark.sql.catalog.{self.catalog_name}.glue.id", self.catalog_id)
            .config(
                f"spark.sql.catalog.{self.catalog_name}.s3.endpoint",
                self.object_store_endpoint,
            )
            .config(
                f"spark.sql.catalog.{self.catalog_name}.s3.path-style-access",
                "true",
            )
            .enableHiveSupport()
            .getOrCreate()
        )
