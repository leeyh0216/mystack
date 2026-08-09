<!-- doc-id: client-compatibility-matrix -->
<!-- lang: ko -->

[한국어](client-matrix.ko.md) | [English](client-matrix.md)

# 클라이언트와 라이브러리 호환성

<!-- toc:start -->
## 목차

- [상태 기준](#상태-기준)
- [검증한 클라이언트](#검증한-클라이언트)
- [제한된 클라이언트 집합](#제한된-클라이언트-집합)
- [현재 제외](#현재-제외)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 AWS 프로토콜을 사용하는 외부 클라이언트가 Mystack의 단일 공개 엔드포인트에서 실제로
검증됐는지 기록합니다. 특정 라이브러리의 일부 경로 통과를 해당 라이브러리 전체 지원으로 확대해서
해석하지 않습니다.

<!-- section: levels -->
## 상태 기준

| 상태 | 의미 |
| --- | --- |
| `E2E` | 공개 Proxy와 Docker 실행 환경을 통한 데이터·메타데이터 왕복을 CI에서 실행 |
| `CONTRACT` | 공개 Proxy를 통한 프로토콜 API 작업과 오류를 자동 검증 |
| `CANDIDATE` | 공식 어댑터가 범위와 맞지만 아직 자동 검증하지 않음 |
| `OUT_OF_SCOPE` | 현재 제외한 AWS 서비스가 필요함 |

<!-- section: verified -->
## 검증한 클라이언트

GitHub Actions는 테스트가 선언한 정확한 버전의 호환성 사례를 사용합니다. 관리자는 형식이 지정된
프로필을 만들거나 재사용하고, 실제 `contract` 또는 `e2e` 테스트에 검증한 시나리오와 API 작업을
선언합니다. 수집기는 잘못된 표식, 잠금 파일/실행 환경 불일치, 알 수 없는 모델 API 작업, 누락된
지원 검증, 사례 선택 차이를 테스트 본문 실행 전에 거부합니다. 원본 정책은
`contracts/compatibility-scope-policy.yaml`이며, CI는 상세 사례 보고서를
`ci-artifacts/compatibility/` 아래에 만듭니다.

| 클라이언트 | 고정 버전 | 상태 | 검증 경로 |
| --- | --- | --- | --- |
| boto3/botocore | 1.43.66 | `CONTRACT`, `E2E` | EMR 13개와 Glue Catalog 28개 API 작업, S3 시험 데이터 |
| AWS SDK for pandas | 3.17.0 | `E2E` | partitioned Parquet write/read, Glue database/table/partition 등록과 조회, S3 HEAD |
| Spark Glue Hive 클라이언트 | Glue 5.0 / Spark 3.5.4 | `E2E` | 복합 형식 Parquet 테이블 생성/삽입/읽기 |
| Apache Iceberg Java GlueCatalog | 1.7.1 | `E2E` | create/read/write/evolution, COW/MOR DML, time travel, ref, 메타데이터/maintenance procedure, concurrent retry |

AWS SDK for pandas 시험은 `AWS_ENDPOINT_URL_GLUE`와 `AWS_ENDPOINT_URL_S3`를 모두 공개 Proxy로
지정합니다. `wr.catalog.create_database`, `wr.catalog.get_table_types`, `wr.s3.to_parquet`,
`wr.s3.read_parquet`와 boto3 Glue table/partition 조회가 한 시나리오에 있습니다. Athena,
Redshift, Lake Formation API를 사용하는 함수까지 지원한다는 뜻은 아닙니다.

<!-- section: candidates -->
## 제한된 클라이언트 집합

호환성 표는 의도적으로 boto3/botocore, AWS SDK for pandas, Spark Hive 클라이언트, Apache
Iceberg Java GlueCatalog로 제한합니다. 다른 클라이언트 추가는 이후 별도 범위 결정이 필요하며
암묵적인 할 일 항목이 아닙니다.

<!-- section: exclusions -->
## 현재 제외

`wr.athena.*`, PyAthena, dbt-athena는 Athena 제어 영역과 쿼리 실행이 필요하므로 현재 호환성
범위가 아닙니다. AWS SDK for pandas의 Glue/S3 E2E 성공도 이 함수를 포함하지 않습니다. Glue Job,
JobRun, Crawler를 사용하는 라이브러리 경로도 지원 범위에서 제외합니다. PyIceberg, Flink, Trino,
Glue Iceberg REST 엔드포인트, 계정 간/리전 간 동작, IAM, Lake Formation, 인증, 인가는 명시적으로
제외합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [Amazon S3 HeadObject API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
