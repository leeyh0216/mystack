"""Spark-side Glue Iceberg table optimizer process.

Official references:
- https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html
- https://iceberg.apache.org/docs/1.7.1/spark-procedures/
- https://iceberg.apache.org/javadoc/1.7.1/org/apache/iceberg/ExpireSnapshots.html
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

_RESULT_PREFIX = "MYSTACK_TABLE_OPTIMIZER_RESULT="


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-file", type=Path, required=True)
    parser.add_argument("--catalog-endpoint", required=True)
    parser.add_argument("--object-store-endpoint", required=True)
    parser.add_argument(
        "--object-store-path-style",
        required=True,
        choices=("true", "false"),
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--catalog-name", required=True)
    args = parser.parse_args()
    work = json.loads(args.work_file.read_text(encoding="utf-8"))
    spark = _spark_session(work, args)
    started = time.monotonic()
    try:
        optimizer_type = work["optimizer_type"]
        if optimizer_type == "compaction":
            metrics = _compact(spark, work, args.catalog_name)
        elif optimizer_type == "retention":
            metrics = _retain(spark, work, args.catalog_name)
        elif optimizer_type == "orphan_file_deletion":
            metrics = _delete_orphans(spark, work, args.catalog_name)
        else:
            raise ValueError(f"Unsupported optimizer type {optimizer_type!r}")
        duration_hours = (time.monotonic() - started) / 3600.0
        metrics.setdefault("DpuHours", 0.0)
        metrics.setdefault("NumberOfDpus", 0)
        metrics.setdefault("JobDurationInHour", duration_hours)
        print(_RESULT_PREFIX + json.dumps({"metrics": metrics}, sort_keys=True))
    finally:
        spark.stop()


def _spark_session(work: dict, args):
    from pyspark.sql import SparkSession

    bucket = urlsplit(work["table_location"]).netloc
    builder = (
        SparkSession.builder.appName(
            f"mystack-glue-{work['optimizer_type']}-{work['database_name']}-{work['table_name']}"
        )
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
        .config(f"spark.sql.catalog.{args.catalog_name}.warehouse", f"s3://{bucket}/warehouse")
        .config(
            f"spark.sql.catalog.{args.catalog_name}.glue.endpoint",
            args.catalog_endpoint,
        )
        .config(
            f"spark.sql.catalog.{args.catalog_name}.glue.id",
            work["catalog_id"],
        )
        .config("spark.hadoop.aws.region", args.region)
        .config(
            f"spark.sql.catalog.{args.catalog_name}.s3.endpoint",
            args.object_store_endpoint,
        )
        .config(
            f"spark.sql.catalog.{args.catalog_name}.s3.path-style-access",
            args.object_store_path_style,
        )
    )
    for key, value in _hadoop_s3_configuration(
        args.object_store_endpoint,
        path_style=args.object_store_path_style == "true",
    ).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def _hadoop_s3_configuration(endpoint: str, *, path_style: bool) -> dict[str, str]:
    """Configure S3A used by Iceberg actions separately from Iceberg S3FileIO."""

    return {
        "spark.hadoop.fs.s3a.endpoint": endpoint,
        "spark.hadoop.fs.s3a.path.style.access": str(path_style).lower(),
        "spark.hadoop.fs.s3a.connection.ssl.enabled": str(
            urlsplit(endpoint).scheme == "https"
        ).lower(),
    }


def _compact(spark, work: dict, catalog_name: str) -> dict:
    iceberg = work["configuration"]["compactionConfiguration"]["icebergConfiguration"]
    strategy = iceberg["strategy"]
    procedure_strategy = "sort" if strategy == "z-order" else strategy
    options = {
        "min-input-files": str(iceberg["minInputFiles"]),
        "delete-file-threshold": str(iceberg["deleteFileThreshold"]),
    }
    arguments = [
        f"table => '{_table_argument(work)}'",
        f"strategy => '{procedure_strategy}'",
    ]
    if strategy == "z-order":
        columns = _default_sort_columns(
            spark,
            catalog_name,
            work["database_name"],
            work["table_name"],
        )
        arguments.append(f"sort_order => '{_literal(_zorder(columns))}'")
    arguments.append(f"options => {_sql_map(options)}")
    result = spark.sql(
        f"CALL {_identifier(catalog_name)}.system.rewrite_data_files({', '.join(arguments)})"
    )
    row = result.collect()[0].asDict(recursive=True)
    return {
        "NumberOfBytesCompacted": int(row.get("rewritten_bytes_count", 0)),
        "NumberOfFilesCompacted": int(row.get("rewritten_data_files_count", 0)),
    }


def _retain(spark, work: dict, catalog_name: str) -> dict:
    iceberg = work["configuration"]["retentionConfiguration"]["icebergConfiguration"]
    cutoff = datetime.now(UTC) - timedelta(days=iceberg["snapshotRetentionPeriodInDays"])
    if iceberg["cleanExpiredFiles"]:
        result = spark.sql(
            f"CALL {_identifier(catalog_name)}.system.expire_snapshots("
            f"table => '{_table_argument(work)}', "
            f"older_than => TIMESTAMP '{cutoff.strftime('%Y-%m-%d %H:%M:%S')}', "
            f"retain_last => {int(iceberg['numberOfSnapshotsToRetain'])})"
        )
        row = result.collect()[0].asDict(recursive=True)
    else:
        _expire_metadata_only(
            spark,
            catalog_name,
            work["database_name"],
            work["table_name"],
            int(cutoff.timestamp() * 1000),
            int(iceberg["numberOfSnapshotsToRetain"]),
        )
        row = {}
    return {
        "NumberOfDataFilesDeleted": int(row.get("deleted_data_files_count", 0)),
        "NumberOfManifestFilesDeleted": int(row.get("deleted_manifest_files_count", 0)),
        "NumberOfManifestListsDeleted": int(row.get("deleted_manifest_lists_count", 0)),
    }


def _expire_metadata_only(
    spark,
    catalog_name: str,
    database_name: str,
    table_name: str,
    cutoff_millis: int,
    retain_last: int,
) -> None:
    """Use Iceberg's official Java API because the Spark procedure always cleans files."""

    iceberg_table = _iceberg_table(spark, catalog_name, database_name, table_name)
    (
        iceberg_table.expireSnapshots()
        .expireOlderThan(cutoff_millis)
        .retainLast(retain_last)
        .cleanExpiredFiles(False)
        .commit()
    )


def _default_sort_columns(
    spark,
    catalog_name: str,
    database_name: str,
    table_name: str,
) -> tuple[str, ...]:
    """Resolve the current Iceberg sort order required by Glue z-order compaction."""

    iceberg_table = _iceberg_table(spark, catalog_name, database_name, table_name)
    fields = list(iceberg_table.sortOrder().fields())
    if not fields:
        raise ValueError(
            "Glue z-order compaction requires an Iceberg table sort order; "
            "define the sort order before enabling or running this strategy"
        )
    columns: list[str] = []
    schema = iceberg_table.schema()
    for field in fields:
        transform = str(field.transform())
        if transform != "identity":
            raise ValueError(
                "Glue z-order emulation requires identity fields in the Iceberg "
                f"sort order, but found transform {transform!r}"
            )
        column_name = schema.findColumnName(field.sourceId())
        if column_name is None:
            raise ValueError(
                f"Iceberg sort field source id {field.sourceId()} is absent from the schema"
            )
        columns.append(str(column_name))
    return tuple(columns)


def _iceberg_table(spark, catalog_name: str, database_name: str, table_name: str):
    gateway = spark.sparkContext._gateway
    jvm = spark.sparkContext._jvm
    namespace = gateway.new_array(jvm.java.lang.String, 1)
    namespace[0] = database_name
    identifier = jvm.org.apache.spark.sql.connector.catalog.Identifier.of(namespace, table_name)
    catalog = spark._jsparkSession.sessionState().catalogManager().catalog(catalog_name)
    return catalog.loadTable(identifier).table()


def _delete_orphans(spark, work: dict, catalog_name: str) -> dict:
    import boto3
    from botocore.config import Config

    iceberg = work["configuration"]["orphanFileDeletionConfiguration"]["icebergConfiguration"]
    cutoff = datetime.now(UTC) - timedelta(days=iceberg["orphanFileRetentionPeriodInDays"])
    rows = spark.sql(
        f"CALL {_identifier(catalog_name)}.system.remove_orphan_files("
        f"table => '{_table_argument(work)}', "
        f"older_than => TIMESTAMP '{cutoff.strftime('%Y-%m-%d %H:%M:%S')}', "
        f"location => '{_literal(iceberg['location'])}', dry_run => true)"
    ).collect()
    s3 = boto3.client(
        "s3",
        endpoint_url=spark.conf.get(f"spark.sql.catalog.{catalog_name}.s3.endpoint"),
        config=Config(s3={"addressing_style": "path"}),
    )
    deleted = 0
    for row in rows:
        location = row.asDict(recursive=True).get("orphan_file_location")
        uri = urlsplit(str(location))
        key = uri.path.lstrip("/")
        metadata = s3.head_object(Bucket=uri.netloc, Key=key)
        modified = metadata["LastModified"].timestamp()
        if work["optimizer_create_time"] < modified < cutoff.timestamp():
            s3.delete_object(Bucket=uri.netloc, Key=key)
            deleted += 1
    return {"NumberOfOrphanFilesDeleted": deleted}


def _table_argument(work: dict) -> str:
    return f"{_identifier(work['database_name'])}.{_identifier(work['table_name'])}"


def _identifier(value: str) -> str:
    return "`" + str(value).replace("`", "``") + "`"


def _literal(value: str) -> str:
    return str(value).replace("'", "''")


def _zorder(columns: tuple[str, ...]) -> str:
    if not columns:
        raise ValueError("Z-order requires at least one sort column")
    return "zorder(" + ",".join(_identifier(column) for column in columns) + ")"


def _sql_map(value: dict[str, str]) -> str:
    items = ", ".join(f"'{_literal(key)}', '{_literal(item)}'" for key, item in value.items())
    return f"map({items})"


if __name__ == "__main__":
    main()
