"""Exercise AWS Glue Open Table Format inputs with the real Iceberg GlueCatalog.

Official references:
- https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html
- https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateIcebergTableInput.html
- https://iceberg.apache.org/spec/#table-metadata
"""

from __future__ import annotations

import json

import boto3
from botocore.config import Config
from pyspark.sql import SparkSession


def exercise_open_table_format(
    spark: SparkSession,
    *,
    catalog_endpoint: str,
    region: str,
    database: str,
    catalog_name: str,
    table: str,
    location: str,
    sdk_timeout_seconds: float,
) -> dict:
    qualified = f"{catalog_name}.`{database}`.`{table}`"
    _event("spark-load", "before")
    initial_columns = spark.table(qualified).columns
    spark.sql(f"INSERT INTO {qualified} (id, category) VALUES (1, 'north')")
    initial_count = spark.table(qualified).count()
    _event("spark-load", "after")

    glue = boto3.client(
        "glue",
        endpoint_url=catalog_endpoint,
        region_name=region,
        config=Config(
            connect_timeout=sdk_timeout_seconds,
            read_timeout=sdk_timeout_seconds,
            retries={"max_attempts": 0},
        ),
    )
    table_document = glue.get_table(DatabaseName=database, Name=table)["Table"]
    schema = {
        "SchemaId": 1,
        "Type": "struct",
        "IdentifierFieldIds": [1],
        "Fields": [
            {"Id": 1, "Name": "id", "Type": "long", "Required": True},
            {"Id": 2, "Name": "category", "Type": "string", "Required": False},
            {"Id": 3, "Name": "note", "Type": "string", "Required": False},
        ],
    }
    _event("boto-update", "before")
    glue.update_table(
        DatabaseName=database,
        Name=table,
        VersionId=table_document["VersionId"],
        UpdateOpenTableFormatInput={
            "UpdateIcebergInput": {
                "UpdateIcebergTableInput": {
                    "Updates": [
                        {"Action": "add-schema", "Schema": schema, "Location": location},
                        {
                            "Action": "set-current-schema",
                            "Schema": schema,
                            "Location": location,
                        },
                    ]
                }
            }
        },
    )
    _event("boto-update", "after")

    spark.catalog.refreshTable(qualified)
    evolved_columns = spark.table(qualified).columns
    spark.sql(f"INSERT INTO {qualified} (id, category, note) VALUES (2, 'south', 'evolved')")
    rows = [row.asDict(recursive=True) for row in spark.sql(f"SELECT * FROM {qualified}").collect()]
    return {
        "iceberg_open_table_format_table": table,
        "iceberg_open_table_format_initial_columns": initial_columns,
        "iceberg_open_table_format_initial_count": initial_count,
        "iceberg_open_table_format_evolved_columns": evolved_columns,
        "iceberg_open_table_format_rows": sorted(rows, key=lambda value: value["id"]),
    }


def _event(name: str, phase: str) -> None:
    print(
        "MYSTACK_E2E_SCENARIO="
        + json.dumps({"name": f"open-table-format-{name}", "phase": phase}, sort_keys=True)
    )
