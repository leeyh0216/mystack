<!-- doc-id: client-workflows -->
<!-- lang: ko -->

[한국어](client-workflows.ko.md) | [English](client-workflows.md)

# 클라이언트별 작업 흐름

<!-- toc:start -->
## 목차

- [작업 흐름 선택](#작업-흐름-선택)
- [하나의 endpoint와 두 서비스](#하나의-endpoint와-두-서비스)
- [AWS CLI와 boto3](#aws-cli와-boto3)
- [AWS SDK for pandas](#aws-sdk-for-pandas)
- [Spark Hive와 Iceberg](#spark-hive와-iceberg)
- [이 문서를 읽는 방법](#이-문서를-읽는-방법)
- [해당 lab 실행](#해당-lab-실행)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서에서는 클라이언트별 요청 경로와 필요한 설정을 먼저 확인한 뒤 예제를 실행합니다. Mystack은
AWS protocol control plane을 위한 로컬 endpoint이며, 모든 AWS 분석 서비스를 대체하지는 않습니다.

<!-- section: choose -->
## 작업 흐름 선택

| 사용하는 도구 | 시작 작업 | 호출 대상 | 검증 상태 |
| --- | --- | --- | --- |
| AWS CLI 또는 boto3 | Glue database/table/partition, EMR cluster/Step API | Public Proxy | 검증됨 |
| AWS SDK for pandas | `wr.catalog`, `wr.s3` Parquet dataset | Proxy를 통한 Glue와 S3 | 수직 경로 검증됨 |
| Spark SQL | Hive metastore 호환 Glue Catalog | Proxy의 Glue, LocalStack S3 | 수직 경로 검증됨 |
| Spark Iceberg | Iceberg `GlueCatalog` | Proxy의 Glue, LocalStack S3 | 수직 경로 검증됨 |

정확한 지원 operation과 version은 [호환성 matrix](compatibility/client-matrix.ko.md)를 확인합니다.

<!-- section: endpoint -->
## 하나의 endpoint와 두 서비스

호스트에서는 모든 AWS control-plane 요청을 `http://localhost:4566`으로 보냅니다. Mystack Compose
network에 연결한 client container에서는 Glue/EMR에 `http://proxy:8080`, S3 object에는
`http://localstack:4566`을 사용합니다. Proxy는 Glue target을 Glue service로, EMR target을 EMR
service로, emulation하지 않는 service를 LocalStack으로 전달합니다.

```text
client -> proxy:8080 -> Glue Catalog API -> SQLite catalog
                  |-> EMR API          -> local Spark Step runtime
                  `-> S3 API           -> LocalStack S3
```

SDK client에는 아래 local credential을 설정합니다.

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_EC2_METADATA_DISABLED=true
```

<!-- section: aws -->
## AWS CLI와 boto3

두 service에 동일한 public endpoint를 사용합니다. Glue 호출은 Catalog metadata를 생성하거나 읽고,
EMR 호출은 local cluster model을 생성하며 Step 요청 시 Spark 작업을 queue에 넣습니다.

```bash
aws --endpoint-url http://localhost:4566 glue create-database \
  --database-input Name=analytics
aws --endpoint-url http://localhost:4566 glue get-databases
aws --endpoint-url http://localhost:4566 emr list-clusters
```

Step은 S3 bucket 생성, application upload, `RunJobFlow`, `WAITING` 대기, `AddJobFlowSteps` 순서로
제출합니다. 전체 argument vector와 log 위치는 [EMR 안내](emr.ko.md)를 따릅니다. 인수는 shell이 아닌
`spark-submit`에 직접 전달됩니다.

<!-- section: pandas -->
## AWS SDK for pandas

AWS SDK for pandas의 catalog/S3 helper는 내부적으로 boto3 client를 사용합니다. 두 endpoint를 Mystack으로
설정한 뒤 일반 dataset write/read 흐름을 사용합니다.

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

이 경로는 dataset metadata에 Glue, file에 S3를 사용합니다. Athena 기반 helper는 현재 로컬 범위 밖입니다.

<!-- section: spark -->
## Spark Hive와 Iceberg

Spark는 metadata에는 Glue 호환 Catalog, data에는 LocalStack을 연결합니다. Compose client container에서는
두 endpoint를 별도로 설정합니다.

```text
# Hive metastore 호환 Catalog
spark.hadoop.hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory
spark.hadoop.aws.glue.endpoint=http://proxy:8080

# 공통 S3A 설정
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

Hive table에는 Hive SQL을, Iceberg table에는 `mystack.namespace.table` 이름을 사용합니다. data와
Iceberg metadata는 S3에서 client가 소유하고, Mystack은 Glue Catalog 요청과 versioning을 처리합니다.

<!-- section: format -->
## 이 문서를 읽는 방법

이 흐름은 AWS, Spark, Trino 문서의 task 중심 형식을 따릅니다. workload를 고르고, 사전조건을 확인한 뒤,
최소 설정을 적용하고, 하나의 완전한 command 또는 program을 실행한 다음 결과와 제한을 확인합니다. Trino는
connector의 metastore와 filesystem 사전조건을 설명하는 형식 참고 자료이며 Mystack 지원 주장에는 포함되지
않습니다. workflow에 client를 채택하기 전 [지원 범위](support-scope.ko.md)와 호환성 matrix를 확인합니다.

<!-- section: labs -->
## 해당 lab 실행

아래 folder에는 client image, Compose override, sample workload, stack과 client를 함께 시작하는 명령이
있습니다.

- `examples/clients/aws/` — AWS CLI, boto3, AWS SDK for pandas
- `examples/clients/spark/` — Spark Hive와 Iceberg

선택한 folder의 `README.md`를 실행합니다. lab은 repository의 기본 `compose.yaml`을 사용하므로 cloud
credential이나 AWS account가 필요하지 않습니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS SDK endpoint 설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Spark SQL에서 AWS Glue Data Catalog 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
- [Trino Hive connector](https://trino.io/docs/current/connector/hive.html)
- [Trino Glue metastore property](https://trino.io/docs/current/object-storage/metastores.html)
