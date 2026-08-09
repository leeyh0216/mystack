"""Client-facing Spark Catalog configuration remains one reusable immutable component."""

from mystack.glue.runtime.spark_catalog import GlueSparkCatalogSettings


def test_glue_spark_catalog_settings_emit_hive_iceberg_and_s3_options() -> None:
    settings = GlueSparkCatalogSettings(
        catalog_endpoint="http://proxy:8080",
        object_store_endpoint="http://localstack:4566",
        region="us-east-1",
        catalog_id="000000000000",
        bucket="client-lab",
        catalog_name="mystack",
    )

    options = dict(settings.options())

    assert options["spark.hadoop.aws.glue.endpoint"] == "http://proxy:8080"
    assert options["spark.hadoop.fs.s3a.endpoint"] == "http://localstack:4566"
    assert (
        options["spark.sql.catalog.mystack.catalog-impl"]
        == "org.apache.iceberg.aws.glue.GlueCatalog"
    )
    assert options["spark.sql.catalog.mystack.warehouse"] == "s3://client-lab/warehouse"
