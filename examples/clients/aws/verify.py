"""One public-endpoint AWS client smoke workflow for Mystack."""

from __future__ import annotations

import os

import awswrangler as wr
import boto3
import pandas as pd
from botocore.exceptions import ClientError

ENDPOINT = os.environ["AWS_ENDPOINT_URL"]
BUCKET = "mystack-client-lab"
DATABASE = "client_lab"


def _create_once(client: object, operation: str, **kwargs: object) -> None:
    try:
        getattr(client, operation)(**kwargs)
    except ClientError as error:
        tolerated = {"AlreadyExistsException", "BucketAlreadyOwnedByYou"}
        if error.response["Error"]["Code"] not in tolerated:
            raise


def main() -> None:
    session = boto3.Session(region_name="us-east-1")
    s3 = session.client("s3", endpoint_url=ENDPOINT)
    glue = session.client("glue", endpoint_url=ENDPOINT)
    emr = session.client("emr", endpoint_url=ENDPOINT)
    _create_once(s3, "create_bucket", Bucket=BUCKET)
    _create_once(glue, "create_database", DatabaseInput={"Name": DATABASE})
    wr.s3.to_parquet(
        df=pd.DataFrame({"id": [1, 2], "day": ["2026-08-08", "2026-08-09"]}),
        path=f"s3://{BUCKET}/events/",
        dataset=True,
        database=DATABASE,
        table="events",
        partition_cols=["day"],
        boto3_session=session,
    )
    table = glue.get_table(DatabaseName=DATABASE, Name="events")["Table"]
    print(
        {
            "glue_database": DATABASE,
            "glue_table": table["Name"],
            "emr_cluster_count": len(emr.list_clusters()["Clusters"]),
        }
    )


if __name__ == "__main__":
    main()
