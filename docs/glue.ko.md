<!-- doc-id: glue-guide -->
<!-- lang: ko -->

[한국어](glue.ko.md) | [English](glue.md)

# Glue Data Catalog

<!-- toc:start -->
## 목차

- [Endpoint 선택](#endpoint-선택)
- [boto3 사용](#boto3-사용)
- [AWS SDK for pandas 사용](#aws-sdk-for-pandas-사용)
- [Spark Hive 또는 Iceberg 사용](#spark-hive-또는-iceberg-사용)
- [Metadata 확인](#metadata-확인)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 boto3, AWS SDK for pandas, Spark Hive, Apache Iceberg를 통해 Catalog metadata를 저장하는
애플리케이션을 위한 안내입니다.

요청, persistence, Iceberg commit 경계는 선택적인 [Glue Catalog 아키텍처](glue-catalog-architecture.ko.md)를 참고하세요.

<!-- section: start -->
## Endpoint 선택

Host에서는 `http://localhost:4566`을 사용합니다. Mystack Compose network의 Spark 또는 application
container에서는 Catalog에 `http://proxy:8080`, S3에 `http://localstack:4566`을 사용합니다.

AWS client를 사용하기 전에 로컬 개발용 credential을 설정합니다.

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

<!-- section: boto3 -->
## boto3 사용

Glue client를 생성할 때 로컬 endpoint를 전달합니다.

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
## AWS SDK for pandas 사용

Dataset을 만들기 전에 Glue와 S3를 모두 Mystack으로 지정합니다.

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
## Spark Hive 또는 Iceberg 사용

선택한 runtime에 필요한 Glue client와 Iceberg dependency를 포함해 Spark를 실행합니다. Mystack
network의 Spark container에서는 아래 값으로 Catalog와 S3 endpoint를 설정합니다.

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

검증된 client/runtime 조합은 [Client 호환성 표](compatibility/client-matrix.ko.md)에서 선택하고,
endpoint와 runtime 설정은 [설정 reference](configuration.ko.md)에서 변경합니다.

<!-- section: inspect -->
## Metadata 확인

[Glue UI](http://localhost:4566/_mystack/ui/glue/)에서 database, table, schema, partition을 탐색합니다.
진단과 구조화 log는 [운영 안내](operations.ko.md)에서 확인합니다.

<!-- section: sources -->
## 공식 참고 자료

- [Spark Hive metastore로 AWS Glue Data Catalog 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [AWS Glue에서 Apache Iceberg 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
