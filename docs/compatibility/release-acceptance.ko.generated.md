[English](release-acceptance.generated.md)

# Catalog release 수용 범위 (생성됨)

<!-- toc:start -->
## 목차

- [Release-blocking 보장](#release-blocking-보장)
- [명시적 제외](#명시적-제외)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 파일은 주석 pytest 증거와 `contracts/compatibility-scope-policy.yaml`에서 생성됩니다. 직접 수정하지 마세요. 아래 모든 case는 `required`이며 release 게시 전에 통과해야 합니다.

Release 수용 범위는 주석 테스트에서 수집한 정확한 client, runtime, operation, scenario로 제한하며 AWS Glue 또는 EMR 전체 호환성을 의미하지 않습니다.

수용 근거: `9634e877ae9bb79ea2ce9670f2929cc190bdc8c7a48e69fa6cda10bc2fcf928d`

## Release-blocking 보장

| 영역 | 보장 | Case | 고정 버전 | Scenario | 근거 | 공식 출처 |
| --- | --- | --- | --- | --- | --- | --- |
| `glue-control-plane-errors` — Glue Catalog API와 결정적 오류 | 주석으로 선언한 모든 Glue Catalog operation이 service boundary를 통과하고 공개 Proxy 경로를 검증하며, 문서화한 로컬 오류 catalog의 전체성과 순서를 유지합니다. | `boto3-botocore-1.43.66-contract`<br>`boto3-botocore-1.43.66-public-proxy` | boto3 `1.43.66`<br>botocore `1.43.66` | `glue-data-catalog`<br>`modeled-service-errors`<br>`glue-operations-through-public-proxy` | [contracts/api-coverage.generated.json](../../contracts/api-coverage.generated.json)<br>[contracts/glue-error-conditions.yaml](../../contracts/glue-error-conditions.yaml)<br>[docs/compatibility/api-coverage.ko.generated.md](../../docs/compatibility/api-coverage.ko.generated.md)<br>[docs/compatibility/glue-errors.ko.generated.md](../../docs/compatibility/glue-errors.ko.generated.md) | [botocore-models](https://github.com/boto/botocore/tree/develop/botocore/data) |
| `aws-sdk-pandas` — AWS SDK for pandas Glue/S3 왕복 | 주석으로 선언한 AWS SDK for pandas profile이 공개 Proxy를 통해 partitioned Parquet을 쓰고 읽으며 Glue database, table, partition과 S3 metadata를 등록하고 조회합니다. | `awswrangler-3.17.0-glue-s3` | awswrangler `3.17.0`<br>boto3 `1.43.66`<br>botocore `1.43.66` | `parquet-glue-s3-round-trip` | [tests/e2e/test_awswrangler.py](../../tests/e2e/test_awswrangler.py)<br>[docs/compatibility/client-matrix.ko.md](../../docs/compatibility/client-matrix.ko.md) | [aws-sdk-pandas](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) |
| `spark-hive` — Spark Hive catalog 동작 | 주석으로 선언한 Glue 5 Spark Hive client로 complex type, type 기반 partition pruning, partition DDL과 repair, 지원하는 ALTER TABLE metadata 변형을 검증합니다. | `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | boto3 `1.43.66`<br>botocore `1.43.66`<br>glue `5.0`<br>iceberg `1.7.1`<br>spark `3.5.4` | `hive-complex-types`<br>`hive-partition-pruning`<br>`hive-partition-ddl-repair`<br>`hive-table-alter` | [tests/e2e/test_glue_spark_catalog.py](../../tests/e2e/test_glue_spark_catalog.py)<br>[docs/protocols/glue-partition-expressions.ko.md](../../docs/protocols/glue-partition-expressions.ko.md)<br>[docs/protocols/glue-hive-partition-ddl.ko.md](../../docs/protocols/glue-hive-partition-ddl.ko.md)<br>[docs/protocols/glue-hive-table-alter.ko.md](../../docs/protocols/glue-hive-table-alter.ko.md) | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)<br>[glue-hive](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) |
| `iceberg` — Iceberg Java GlueCatalog lifecycle | 주석으로 선언한 Glue 5 profile에서 Open Table Format input, create/read/write/evolution, row-level DML, snapshot과 ref, maintenance procedure, managed optimizer, rename/drop/purge, concurrent commit retry를 검증합니다. | `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | boto3 `1.43.66`<br>botocore `1.43.66`<br>glue `5.0`<br>iceberg `1.7.1`<br>spark `3.5.4` | `iceberg-open-table-format-input`<br>`iceberg-create-append-read-evolve`<br>`iceberg-partition-schema-sort-evolution`<br>`iceberg-row-level-dml`<br>`iceberg-snapshots-refs-procedures`<br>`iceberg-managed-table-optimizers`<br>`iceberg-rename-drop-purge`<br>`iceberg-multi-container-contention` | [tests/e2e/test_glue_spark_catalog.py](../../tests/e2e/test_glue_spark_catalog.py)<br>[docs/protocols/glue-open-table-format.ko.md](../../docs/protocols/glue-open-table-format.ko.md)<br>[docs/protocols/glue-iceberg-evolution.ko.md](../../docs/protocols/glue-iceberg-evolution.ko.md)<br>[docs/protocols/glue-iceberg-row-level-dml.ko.md](../../docs/protocols/glue-iceberg-row-level-dml.ko.md)<br>[docs/protocols/glue-iceberg-snapshots-refs-procedures.ko.md](../../docs/protocols/glue-iceberg-snapshots-refs-procedures.ko.md)<br>[docs/protocols/glue-table-optimizers.ko.md](../../docs/protocols/glue-table-optimizers.ko.md)<br>[docs/protocols/glue-iceberg-lifecycle.ko.md](../../docs/protocols/glue-iceberg-lifecycle.ko.md)<br>[docs/protocols/glue-iceberg-commits.ko.md](../../docs/protocols/glue-iceberg-commits.ko.md) | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)<br>[glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)<br>[glue-open-table-format](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html)<br>[glue-table-optimizers](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html)<br>[iceberg-evolution](https://iceberg.apache.org/docs/1.7.1/evolution/)<br>[iceberg-spark-writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/)<br>[iceberg-configuration](https://iceberg.apache.org/docs/1.7.1/configuration/)<br>[iceberg-spark-queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/)<br>[iceberg-spark-ddl](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)<br>[iceberg-spark-procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/)<br>[iceberg-branching](https://iceberg.apache.org/docs/1.7.1/branching/)<br>[iceberg-glue-catalog-source](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416) |
| `emr-pyspark-s3` — EMR PySpark와 LocalStack S3 회귀 | boto3로 emulated EMR cluster를 생성하고 제어하며 bootstrap action, S3 artifact download, local PySpark 실행, 취소, lifecycle, log 게시가 계속 동작함을 검증합니다. | `boto3-botocore-1.43.66-contract`<br>`emr-7.8.0-spark-3.5.4` | boto3 `1.43.66`<br>botocore `1.43.66`<br>emr `7.8.0`<br>spark `3.5.4` | `emr-control-plane`<br>`bootstrap-s3-spark-step-lifecycle` | [emr/tests/test_boto3_contract.py](../../emr/tests/test_boto3_contract.py)<br>[tests/e2e/test_emr_spark.py](../../tests/e2e/test_emr_spark.py)<br>[docs/protocols/emr-log-layout.ko.md](../../docs/protocols/emr-log-layout.ko.md)<br>[docs/testing.ko.md](../../docs/testing.ko.md) | [botocore-models](https://github.com/boto/botocore/tree/develop/botocore/data)<br>[emr-7.8.0](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) |

## 명시적 제외

| 영역 | 제외 이유 | 공식 출처 |
| --- | --- | --- |
| `glue-compute` — Glue compute service | Job, JobRun, Crawler와 이를 사용하는 client 경로는 이번 catalog-store release 범위 밖입니다. | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) |
| `security-and-cloud-boundaries` — 보안과 cloud account 경계 | 인증, 인가, IAM, Lake Formation, cross-account, cross-Region 의미론은 emulation하지 않습니다. | [glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) |
| `additional-catalog-clients` — 추가 catalog client | PyIceberg, Flink, Trino, Glue Iceberg REST endpoint는 호환성을 보장하지 않습니다. | [glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) |
| `external-fidelity` — 외부 AWS와 분산 runtime 재현도 | 실 AWS 비교 시험과 물리 EC2, YARN, HDFS 분산 환경 재현은 제외합니다. | [emr-7.8.0](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) |

## 공식 참고 자료

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) (`aws-sdk-pandas`)
- [botocore AWS service models](https://github.com/boto/botocore/tree/develop/botocore/data) (`botocore-models`)
- [Amazon EMR 7.8.0 release](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) (`emr-7.8.0`)
- [AWS Glue 5.0 migration guide](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) (`glue-5.0`)
- [AWS Glue Data Catalog as the Spark Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) (`glue-hive`)
- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) (`glue-iceberg`)
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
