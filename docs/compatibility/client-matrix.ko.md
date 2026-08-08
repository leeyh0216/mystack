<!-- doc-id: client-compatibility-matrix -->
<!-- lang: ko -->

[한국어](client-matrix.ko.md) | [English](client-matrix.md)

# Client와 library 호환성

이 문서는 AWS protocol을 사용하는 외부 client가 Mystack의 단일 공개 endpoint에서 실제로
검증됐는지 기록합니다. 특정 library의 일부 경로 통과를 해당 library 전체 지원으로 확대해서
해석하지 않습니다.

<!-- section: levels -->
## 상태 기준

| 상태 | 의미 |
| --- | --- |
| `E2E` | 공개 Proxy와 Docker runtime을 통한 data·metadata 왕복을 CI에서 실행 |
| `CONTRACT` | 공개 Proxy를 통한 protocol operation과 오류를 자동 검증 |
| `CANDIDATE` | 공식 adapter가 범위와 맞지만 아직 자동 검증하지 않음 |
| `OUT_OF_SCOPE` | 현재 제외한 AWS service가 필요함 |

<!-- section: verified -->
## 검증한 Client

[생성된 정확한 version 근거](client-matrix.ko.generated.md)는 GitHub Actions가 사용하는 기준
목록입니다. 관리자는 `compatibility/cases.yaml`에 명시적 case 한 개를 추가합니다. compiler는
시험 시작 전에 알 수 없는 field, 변경 가능한 artifact, 잘못된 runtime 조합과 service model
변경을 거부합니다.

| Client | 고정 버전 | 상태 | 검증 경로 |
| --- | --- | --- | --- |
| boto3/botocore | 1.43.66 | `CONTRACT`, `E2E` | EMR 13개와 Glue Catalog 22개 operation, S3 시험 데이터 |
| AWS SDK for pandas | 3.17.0 | `E2E` | partitioned Parquet write/read, Glue database/table/partition 등록과 조회, S3 HEAD |
| Spark Glue Hive client | Glue 5.0 / Spark 3.5.4 | `E2E` | complex type Parquet table create/insert/read |
| Apache Iceberg Java GlueCatalog | 1.7.1 | `E2E` | namespace/table create, append, read, schema evolution |

AWS SDK for pandas 시험은 `AWS_ENDPOINT_URL_GLUE`와 `AWS_ENDPOINT_URL_S3`를 모두 공개 Proxy로
지정합니다. `wr.catalog.create_database`, `wr.catalog.get_table_types`, `wr.s3.to_parquet`,
`wr.s3.read_parquet`와 boto3 Glue table/partition 조회가 한 시나리오에 있습니다. Athena,
Redshift, Lake Formation API를 사용하는 함수까지 지원한다는 뜻은 아닙니다.

<!-- section: candidates -->
## 다음 검증 후보

| 우선순위 | Client | 가치 | 권장 실행 계층 |
| --- | --- | --- | --- |
| P0 | s3fs/fsspec | Python 생태계의 HEAD, Range GET, ListObjectsV2, multipart 경계를 가볍게 검증 | 일반 Docker E2E |
| P1 | PyIceberg GlueCatalog | Spark와 독립적인 Python Iceberg catalog/file I/O와 Glue 의미를 검증 | 일반 Docker E2E |
| P2 | Trino Hive/Iceberg connector | 독립 JVM SQL engine으로 Glue metastore, partition, statistics 호환성 압박 | nightly Docker E2E |
| P2 | DuckDB httpfs/Parquet | HEAD, Range GET, glob, multipart S3 fallback을 독립 native client로 검증 | 일반 Docker E2E |
| P3 | Flink Iceberg Glue sink | streaming write, schema propagation과 장시간 실행 경계를 검증 | 선택적 nightly E2E |

PyIceberg는 Glue를 native catalog type으로 제공하므로 다음 Glue 호환성 확장에 가장 직접적인
후보입니다. Trino는 image와 초기화 비용이 크고 statistics API 같은 현재 미구현 범위를 호출할 수
있으므로 별도 profile이 적합합니다. DuckDB와 s3fs는 Glue보다 Proxy의 S3 투명성을 빠르게
회귀 검증하는 데 유용합니다.

<!-- section: exclusions -->
## 현재 제외

`wr.athena.*`, PyAthena, dbt-athena는 Athena control plane과 query execution이 필요하므로 현재
호환성 주장이 아닙니다. AWS SDK for pandas의 Glue/S3 E2E 성공도 이 함수들을 포함하지 않습니다.
Glue Job, JobRun, Crawler를 사용하는 library 경로도 지원 범위에서 제외합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [Amazon S3 HeadObject API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [PyIceberg configuration](https://py.iceberg.apache.org/configuration/)
- [Trino metastore configuration](https://trino.io/docs/current/object-storage/metastores.html)
- [DuckDB S3 API support](https://duckdb.org/docs/current/core_extensions/httpfs/s3api)
- [s3fs documentation](https://s3fs.readthedocs.io/en/latest/)
- [Flink CDC Iceberg Glue example](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.6/docs/connectors/pipeline-connectors/iceberg/)
