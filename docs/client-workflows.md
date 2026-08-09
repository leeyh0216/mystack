<!-- doc-id: client-workflows -->
<!-- lang: en -->

[한국어](client-workflows.ko.md) | [English](client-workflows.md)

# Client workflows

<!-- toc:start -->
## Contents

- [Choose the right workflow](#choose-the-right-workflow)
- [One endpoint, two services](#one-endpoint-two-services)
- [AWS CLI and boto3](#aws-cli-and-boto3)
- [AWS SDK for pandas](#aws-sdk-for-pandas)
- [Spark Hive and Iceberg](#spark-hive-and-iceberg)
- [How to read this guide](#how-to-read-this-guide)
- [Run the matching lab](#run-the-matching-lab)
- [Official sources](#official-sources)
<!-- toc:end -->

Use this page to choose a client and follow the request path before copying configuration. Mystack
is one local endpoint for AWS-protocol control-plane requests; it is not a replacement for every
AWS analytics service.

<!-- section: choose -->
## Choose the right workflow

| You are using | Start with | What it calls | Verification status |
| --- | --- | --- | --- |
| AWS CLI or boto3 | Glue database/table/partition APIs; EMR cluster/Step APIs | Public Proxy | Verified |
| AWS SDK for pandas | `wr.catalog` plus `wr.s3` Parquet datasets | Glue and S3 through Proxy | Verified vertical path |
| Spark SQL | Hive metastore-compatible Glue Catalog | Glue through Proxy; S3 through LocalStack | Verified vertical path |
| Spark Iceberg | Iceberg `GlueCatalog` | Glue through Proxy; S3 through LocalStack | Verified vertical path |

For the exact verified operations and versions, use the [compatibility matrix](compatibility/client-matrix.md).

<!-- section: endpoint -->
## One endpoint, two services

From the host, send all AWS control-plane requests to `http://localhost:4566`. From a client
container that joins the Mystack Compose network, use `http://proxy:8080` for Glue and EMR, and
`http://localstack:4566` for S3 objects. The Proxy routes Glue targets to the Glue service, EMR
targets to the EMR service, and non-emulated services to LocalStack.

```text
client -> proxy:8080 -> Glue Catalog API -> SQLite catalog
                  |-> EMR API          -> local Spark Step runtime
                  `-> S3 API           -> LocalStack S3
```

Set local credentials for every SDK-based client:

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_EC2_METADATA_DISABLED=true
```

<!-- section: aws -->
## AWS CLI and boto3

Use the same public endpoint for both services. A Glue call creates or reads Catalog metadata;
an EMR call creates a local cluster model and queues a Spark Step when requested.

```bash
aws --endpoint-url http://localhost:4566 glue create-database \
  --database-input Name=analytics
aws --endpoint-url http://localhost:4566 glue get-databases
aws --endpoint-url http://localhost:4566 emr list-clusters
```

For a Step, create the S3 bucket first, upload the application, call `RunJobFlow`, wait for
`WAITING`, then call `AddJobFlowSteps`. Follow the [EMR guide](emr.md) for the complete argument
vector and log locations; arguments are passed directly to `spark-submit`, never evaluated by a
shell.

<!-- section: pandas -->
## AWS SDK for pandas

AWS SDK for pandas uses boto3 clients beneath its catalog and S3 helpers. Point both service
endpoints at Mystack, then use a normal dataset write/read flow.

```bash
export AWS_ENDPOINT_URL_GLUE=http://localhost:4566
export AWS_ENDPOINT_URL_S3=http://localhost:4566
```

```python
import awswrangler as wr
import boto3
import pandas as pd

boto3.client("s3", endpoint_url="http://localhost:4566").create_bucket(Bucket="mystack-example")
wr.catalog.create_database(name="analytics")
wr.s3.to_parquet(
    df=pd.DataFrame({"id": [1, 2], "day": ["2026-08-08", "2026-08-09"]}),
    path="s3://mystack-example/events/", dataset=True,
    database="analytics", table="events", partition_cols=["day"],
)
```

This path uses Glue for dataset metadata and S3 for files. Athena-backed helpers remain outside
the local scope.

<!-- section: spark -->
## Spark Hive and Iceberg

Spark connects to the Glue-compatible Catalog for metadata and LocalStack for data. In a Compose
client container, configure the two endpoints separately:

```text
# Hive metastore-compatible Catalog
spark.hadoop.hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory
spark.hadoop.aws.glue.endpoint=http://proxy:8080

# Shared S3A settings
spark.hadoop.fs.s3a.endpoint=http://localstack:4566
spark.hadoop.fs.s3a.path.style.access=true

# Iceberg named catalog
spark.sql.catalog.mystack=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.mystack.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog
spark.sql.catalog.mystack.glue.endpoint=http://proxy:8080
spark.sql.catalog.mystack.s3.endpoint=http://localstack:4566
spark.sql.catalog.mystack.s3.path-style-access=true
spark.sql.catalog.mystack.warehouse=s3://mystack-example/warehouse
```

Use Hive SQL for Hive tables and `mystack.namespace.table` for Iceberg tables. The data and Iceberg
metadata stay client-owned in S3; Mystack owns the Glue Catalog request and its modeled versioning.

<!-- section: format -->
## How to read this guide

The flow follows the task-oriented format used by the AWS, Spark, and Trino documentation: choose
a workload, meet its prerequisites, apply a minimal configuration, run one complete command or
program, then verify the result and read the boundary. Trino is a useful reference for describing a
connector's metastore and filesystem prerequisites; it is not a Mystack support claim. Use the
[support scope](support-scope.md) and compatibility matrix before adopting a client in a workflow.

<!-- section: labs -->
## Run the matching lab

Each folder below contains a client image, a Compose override, sample workload, and a command that
starts the stack and client together:

- `examples/clients/aws/` — AWS CLI, boto3, and AWS SDK for pandas
- `examples/clients/spark/` — Spark Hive and Iceberg

Run the `README.md` in the selected folder. The lab uses the repository's base `compose.yaml`; it
does not require cloud credentials or a running AWS account.

<!-- section: sources -->
## Official sources

- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [AWS Glue Data Catalog with Spark SQL](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
- [Trino Hive connector](https://trino.io/docs/current/connector/hive.html)
- [Trino Glue metastore properties](https://trino.io/docs/current/object-storage/metastores.html)
