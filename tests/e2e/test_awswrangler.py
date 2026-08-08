"""AWS SDK for pandas through the public Mystack endpoint.

Official references:
- https://aws-sdk-pandas.readthedocs.io/en/stable/stubs/awswrangler.s3.to_parquet.html
- https://aws-sdk-pandas.readthedocs.io/en/stable/stubs/awswrangler.s3.read_parquet.html
- https://aws-sdk-pandas.readthedocs.io/en/stable/stubs/awswrangler.catalog.get_table_types.html
- https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
"""

from __future__ import annotations

import uuid
from typing import Any

import awswrangler as wr
import boto3
import pandas as pd
import pytest


@pytest.mark.e2e
def test_aws_sdk_for_pandas_parquet_glue_catalog_round_trip(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write data and metadata, then read both through the same public Proxy."""

    for service in ("GLUE", "S3"):
        monkeypatch.setenv(f"AWS_ENDPOINT_URL_{service}", e2e_settings.endpoint_url)
    monkeypatch.setenv("AWS_DEFAULT_REGION", e2e_settings.region)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", e2e_settings.access_key_id)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", e2e_settings.secret_access_key)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    suffix = uuid.uuid4().hex
    bucket = f"mystack-wrangler-e2e-{suffix}"
    database = f"mystack_wrangler_e2e_{suffix}"
    table = "events"
    root = f"s3://{bucket}/{table}/"
    s3 = aws_clients["s3"]
    glue = aws_clients["glue"]
    session = boto3.Session(
        aws_access_key_id=e2e_settings.access_key_id,
        aws_secret_access_key=e2e_settings.secret_access_key,
        region_name=e2e_settings.region,
    )

    database_created = False
    s3.create_bucket(Bucket=bucket)
    try:
        wr.catalog.create_database(name=database, boto3_session=session)
        database_created = True
        written = wr.s3.to_parquet(
            df=pd.DataFrame(
                {
                    "id": [1, 2],
                    "kind": ["created", "updated"],
                    "day": ["2026-08-08", "2026-08-09"],
                }
            ),
            path=root,
            dataset=True,
            database=database,
            table=table,
            partition_cols=["day"],
            boto3_session=session,
        )
        assert len(written["paths"]) == 2
        for path in written["paths"]:
            key = path.removeprefix(f"s3://{bucket}/")
            assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] > 0

        table_types = wr.catalog.get_table_types(
            database=database,
            table=table,
            boto3_session=session,
        )
        assert table_types == {"id": "bigint", "kind": "string", "day": "string"}
        catalog_table = glue.get_table(DatabaseName=database, Name=table)["Table"]
        assert catalog_table["StorageDescriptor"]["Location"] == root
        partitions = glue.get_partitions(DatabaseName=database, TableName=table)["Partitions"]
        assert sorted(value["Values"] for value in partitions) == [
            ["2026-08-08"],
            ["2026-08-09"],
        ]

        restored = wr.s3.read_parquet(
            path=root,
            dataset=True,
            boto3_session=session,
        ).sort_values("id")
        assert restored[["id", "kind"]].to_dict(orient="records") == [
            {"id": 1, "kind": "created"},
            {"id": 2, "kind": "updated"},
        ]
        assert restored["day"].astype(str).tolist() == ["2026-08-08", "2026-08-09"]
        assert wr.__version__ == "3.17.0"
    finally:
        try:
            if database_created:
                glue.delete_database(Name=database)
        finally:
            objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
            if objects:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": value["Key"]} for value in objects]},
                )
            s3.delete_bucket(Bucket=bucket)
