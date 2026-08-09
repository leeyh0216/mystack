<!-- doc-id: glue-guide -->
<!-- lang: en -->

[한국어](glue.ko.md) | [English](glue.md)

# Glue Data Catalog

<!-- toc:start -->
## Contents

- [Choose an endpoint](#choose-an-endpoint)
- [Use boto3](#use-boto3)
- [Use AWS SDK for pandas](#use-aws-sdk-for-pandas)
- [Use Spark Hive or Iceberg](#use-spark-hive-or-iceberg)
- [Inspect metadata](#inspect-metadata)
- [Official sources](#official-sources)
<!-- toc:end -->

Use this guide when your application stores Catalog metadata through boto3, AWS SDK for pandas,
Spark Hive, or Apache Iceberg.

For the request, persistence, and Iceberg commit boundaries, see the optional [Glue Catalog architecture](glue-catalog-architecture.md).

<!-- section: start -->
## Choose an endpoint

Use `http://localhost:4566` from the host. A Spark or application container on the Mystack Compose
network uses `http://proxy:8080` for the Catalog and `http://localstack:4566` for S3.

Set local development credentials before using an AWS client:

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

<!-- section: boto3 -->
## Use boto3

Pass the local endpoint when constructing the Glue client.

```python
import boto3

glue = boto3.client(
    "glue",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
glue.create_database(DatabaseInput={"Name": "analytics"})
print(glue.get_databases())
```

<!-- section: awswrangler -->
## Use AWS SDK for pandas

Point both Glue and S3 to Mystack before creating datasets.

```bash
export AWS_ENDPOINT_URL_GLUE=http://localhost:4566
export AWS_ENDPOINT_URL_S3=http://localhost:4566
```

```python
import awswrangler as wr
import boto3
import pandas as pd

boto3.client("s3").create_bucket(Bucket="mystack-example")
wr.catalog.create_database(name="analytics")
wr.s3.to_parquet(
    df=pd.DataFrame({"id": [1, 2], "day": ["2026-08-08", "2026-08-09"]}),
    path="s3://mystack-example/events/",
    dataset=True,
    database="analytics",
    table="events",
    partition_cols=["day"],
)
print(wr.s3.read_parquet(path="s3://mystack-example/events/", dataset=True))
```

<!-- section: spark -->
## Use Spark Hive or Iceberg

Run Spark with the Glue client and Iceberg dependencies required by your chosen runtime. For a Spark
container on the Mystack network, configure the Catalog and S3 endpoints with the values below.

```text
# Spark Hive
spark.hadoop.hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory
spark.hadoop.aws.glue.endpoint=http://proxy:8080
spark.hadoop.fs.s3a.endpoint=http://localstack:4566
spark.hadoop.fs.s3a.path.style.access=true

# Iceberg named catalog: mystack
spark.sql.catalog.mystack=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.mystack.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog
spark.sql.catalog.mystack.glue.endpoint=http://proxy:8080
spark.sql.catalog.mystack.s3.endpoint=http://localstack:4566
spark.sql.catalog.mystack.s3.path-style-access=true
spark.sql.catalog.mystack.warehouse=s3://mystack-example/warehouse
```

Use the [client compatibility matrix](compatibility/client-matrix.md) to select a verified
client/runtime path, and the [configuration reference](configuration.md) to change endpoint or
runtime settings.

<!-- section: inspect -->
## Inspect metadata

Open the [Glue UI](http://localhost:4566/_mystack/ui/glue/) to browse databases, tables, schemas,
and partitions. The [operations guide](operations.md) explains diagnostics and structured logs.

<!-- section: sources -->
## Official sources

- [AWS Glue Data Catalog as the Spark Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
