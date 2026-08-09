# 생성된 테스트 선언 호환성 근거

<!-- toc:start -->
## 목차

- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 pytest `mystack_compatibility` annotation에서 결정적으로 생성됩니다. 각 행은 test body를 실행하지 않는 collection 결과로 선택한 CI case입니다.

| Case | Lane | Runtime | 고정 버전 | Scenario | 근거 hash |
| --- | --- | --- | --- | --- | --- |
| `awswrangler-3.17.0-glue-s3` | `required` | `glue-5.0-spark-3.5.4` | awswrangler 3.17.0, boto3 1.43.66, botocore 1.43.66 | parquet-glue-s3-round-trip | `2ca200c2978f172e` |
| `boto3-botocore-1.43.66-contract` | `required` | `python-3.11` | boto3 1.43.66, botocore 1.43.66 | emr-control-plane, glue-data-catalog, modeled-service-errors | `b2acf2470d81cb6b` |
| `boto3-botocore-1.43.66-public-proxy` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66 | glue-operations-through-public-proxy | `19130720ce060698` |
| `emr-7.8.0-spark-3.5.4` | `required` | `emr-7.8.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, emr 7.8.0, spark 3.5.4 | bootstrap-s3-spark-step-lifecycle | `7af9b050b4ac5de8` |
| `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, glue 5.0, iceberg 1.7.1, spark 3.5.4 | hive-complex-types, hive-partition-pruning, hive-partition-ddl-repair, hive-table-alter, iceberg-open-table-format-input, iceberg-create-append-read-evolve, iceberg-partition-schema-sort-evolution, iceberg-row-level-dml, iceberg-snapshots-refs-procedures, iceberg-managed-table-optimizers, iceberg-rename-drop-purge, iceberg-multi-container-contention | `11f660670568d593` |

## 공식 참고 자료

- [공식 자료](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [공식 자료](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html)
- [공식 자료](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [공식 자료](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [공식 자료](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)
- [공식 자료](https://github.com/boto/botocore/tree/develop/botocore/data)
