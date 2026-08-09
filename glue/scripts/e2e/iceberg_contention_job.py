"""One barrier-synchronized real Spark/Iceberg writer for CI contention evidence.

References:
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- https://iceberg.apache.org/docs/1.7.1/reliability/#concurrent-write-operations
- https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/head_object.html
"""

from __future__ import annotations

import argparse
import json
import time

import boto3
from botocore.exceptions import ClientError
from mystack.glue.runtime.spark_catalog import GlueSparkCatalogSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-endpoint", required=True)
    parser.add_argument("--object-store-endpoint", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--catalog-name", required=True)
    parser.add_argument("--barrier-prefix", required=True)
    parser.add_argument("--writer", required=True)
    parser.add_argument("--row-id", required=True, type=int)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    parser.add_argument("--poll-interval-seconds", required=True, type=float)
    args = parser.parse_args()

    spark = GlueSparkCatalogSettings(
        catalog_endpoint=args.catalog_endpoint,
        object_store_endpoint=args.object_store_endpoint,
        region=args.region,
        catalog_id=args.catalog_id,
        bucket=args.bucket,
        catalog_name=args.catalog_name,
    ).create_session(f"mystack-iceberg-contention-{args.writer}")
    s3 = boto3.client("s3", endpoint_url=args.object_store_endpoint, region_name=args.region)
    qualified = f"{args.catalog_name}.`{args.database}`.`{args.table}`"
    try:
        # Resolve the table before releasing the barrier so both JVMs begin from the same
        # catalog generation. Iceberg still owns refresh/retry after a VersionId conflict.
        _ = spark.table(qualified).schema
        s3.put_object(
            Bucket=args.bucket,
            Key=f"{args.barrier_prefix}/ready/{args.writer}",
            Body=b"ready",
        )
        _wait_for_start(
            s3,
            bucket=args.bucket,
            key=f"{args.barrier_prefix}/start",
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        spark.sql(
            f"""
            INSERT INTO {qualified} VALUES
              ({args.row_id}, DATE'2026-08-09',
               MAP('writer', '{args.writer}'), '{args.writer}')
            """
        )
        count = spark.table(qualified).count()
        print(
            "MYSTACK_CONTENTION_RESULT="
            + json.dumps({"writer": args.writer, "count": count}, sort_keys=True)
        )
    finally:
        spark.stop()


def _wait_for_start(
    s3,
    *,
    bucket: str,
    key: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                raise
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Timed out waiting for contention barrier after {timeout_seconds} seconds")


if __name__ == "__main__":
    main()
