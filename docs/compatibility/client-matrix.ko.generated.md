# 생성된 Client 호환성 Matrix

<!-- toc:start -->
## 목차

- [호환성 Case](#호환성-case)
- [실행 구분 정책](#실행-구분-정책)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 파일은 `compatibility/cases.yaml`에서 결정적으로 생성됩니다. 직접 수정하지 마세요. 각 행은 CI가 독립 process에서 실행하는 명시적 조합이며 지원하지 않는 전수 조합을 뜻하지 않습니다.

## 호환성 Case

| Case | 실행 구분 | Runtime | 고정 버전 | Scenario | Evidence |
| --- | --- | --- | --- | --- | --- |
| `awswrangler-3.17.0-glue-s3` | `required` | `glue-5.0-spark-3.5.4` | awswrangler 3.17.0, boto3 1.43.66, botocore 1.43.66 | parquet-glue-s3-round-trip | `74e5c09a57ec0c32` |
| `boto3-botocore-1.43.66-contract` | `required` | `python-3.11` | boto3 1.43.66, botocore 1.43.66 | emr-control-plane, glue-data-catalog, modeled-service-errors | `60bcf2133f5fb289` |
| `boto3-botocore-1.43.66-public-proxy` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66 | glue-operations-through-public-proxy | `8598a4f9863fce32` |
| `emr-7.8.0-spark-3.5.4` | `required` | `emr-7.8.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, emr 7.8.0, spark 3.5.4 | bootstrap-s3-spark-step-lifecycle | `b70383d9abced902` |
| `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, glue 5.0, iceberg 1.7.1, spark 3.5.4 | hive-complex-types, hive-partition-pruning, hive-partition-ddl-repair, hive-table-alter, iceberg-open-table-format-input, iceberg-create-append-read-evolve, iceberg-partition-schema-sort-evolution, iceberg-row-level-dml, iceberg-snapshots-refs-procedures, iceberg-managed-table-optimizers, iceberg-rename-drop-purge, iceberg-multi-container-contention | `4fa3c08945ba9aed` |

## 실행 구분 정책

- `required`: release 게시 전에 반드시 통과해야 함; release_blocking=`true`
- `preview`: 제안한 client 또는 runtime version의 선택 실행 검증; release_blocking=`false`
- `nightly`: 비용이 크거나 탐색적인 조합의 정기 검증; release_blocking=`false`

## 공식 참고 자료

- [Amazon Linux public ECR image](https://gallery.ecr.aws/amazonlinux/amazonlinux) (`amazon-linux-image`)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) (`aws-sdk-pandas`)
- [botocore AWS service models](https://github.com/boto/botocore/tree/develop/botocore/data) (`botocore-models`)
- [Docker Compose in CI](https://docs.docker.com/compose/how-tos/ci-cd/) (`docker-compose`)
- [Amazon EMR 7.8.0 release](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) (`emr-7.8.0`)
- [GitHub Actions shared matrices](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations) (`github-matrix`)
- [AWS Glue 5.0 migration guide](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) (`glue-5.0`)
- [AWS Glue Data Catalog as the Spark Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) (`glue-hive`)
- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) (`glue-iceberg`)
- [AWS Glue libraries public ECR image](https://gallery.ecr.aws/glue/aws-glue-libs) (`glue-libs-image`)
- [AWS Glue Open Table Format CreateTable input](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html) (`glue-open-table-format`)
- [AWS Glue Data Catalog table optimizers](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html) (`glue-table-optimizers`)
- [Apache Iceberg 1.7.1 branching and tagging](https://iceberg.apache.org/docs/1.7.1/branching/) (`iceberg-branching`)
- [Apache Iceberg 1.7.1 configuration](https://iceberg.apache.org/docs/1.7.1/configuration/) (`iceberg-configuration`)
- [Apache Iceberg 1.7.1 evolution](https://iceberg.apache.org/docs/1.7.1/evolution/) (`iceberg-evolution`)
- [Apache Iceberg 1.7.1 GlueCatalog implementation](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416) (`iceberg-glue-catalog-source`)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/) (`iceberg-spark-ddl`)
- [Apache Iceberg 1.7.1 Spark procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/) (`iceberg-spark-procedures`)
- [Apache Iceberg 1.7.1 Spark queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/) (`iceberg-spark-queries`)
- [Apache Iceberg 1.7.1 Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/) (`iceberg-spark-writes`)
- [Python Package Index file API](https://docs.pypi.org/api/json/) (`pypi-file-api`)
- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html) (`pytest`)
- [Apache Spark downloads and release verification](https://spark.apache.org/downloads.html) (`spark-downloads`)
