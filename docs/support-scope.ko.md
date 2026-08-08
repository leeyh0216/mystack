<!-- doc-id: support-scope -->
<!-- lang: ko -->

[한국어](support-scope.ko.md) | [English](support-scope.md)

# 지원 범위

<!-- section: overview -->
## 개요

이 문서는 현재 구현과 장기 목표를 구분합니다. “목표”는 현재 빌드가 이미 호환된다는 뜻이 아닙니다.

| 영역 | 현재 상태 | 목표 |
| --- | --- | --- |
| 확장형 Proxy registry | 구현·단위 테스트 완료 | Proxy 코드 변경 없이 새 AWS JSON/SigV4 emulator 등록 |
| AWS JSON 1.1 codec/model 검증 | 구현·단위 테스트 완료 | EMR/Glue modeled request/response/error 처리 |
| LocalStack fallback | 구현·단위 테스트 완료 | EMR/Glue 외 요청의 투명 전달 |
| EMR control plane | 부분 구현: boto3로 검증한 13개 operation | EMR public API 광범위 호환 |
| EMR bootstrap/Spark | 세로 경로 구현: boto3, S3 bootstrap, Python/JAR Spark 3.5.4 local S3A write와 실행 중 취소 E2E | 더 많은 EMR step 유형과 runtime 정합성 |
| Glue Data Catalog | 부분 구현: boto3로 검증한 database/table/version/partition 22개 operation | UDF를 포함한 나머지 범위 내 Catalog API |
| Glue 사용자 확장 | 구현: stable/application/unsafe v1, mount한 wheel, modeled output 검증, boto3 계약 | 더 많은 서비스 context와 선택적 원격 격리 |
| Spark + Hive + Glue Catalog | 세로 경로 구현: 공식 Glue 5 image, complex type, S3 Parquet E2E | 더 넓은 Hive metadata 의미론 |
| Spark + Iceberg + Glue Catalog | 세로 경로 구현: Iceberg 1.7.1 create/append/read/schema evolution E2E | Partition, transaction, 더 넓은 Iceberg API |
| AWS SDK for pandas | 세로 경로 구현: 3.17.0 partitioned Parquet S3/Glue write/read E2E | 더 넓은 Glue/S3 함수와 추가 client 검증 |
| Web console | 구현: EMR/Glue resource·상태·상세, EMR log, route/thread/task, keyboard/browser E2E | 추가 service별 시각화 |

관리 console은 `/_mystack/console`에서 제공됩니다. Glue metadata는 설정된
`glue.state_file`에 원자적으로 저장됩니다. 현재 partition expression evaluator는 따옴표로
감싼 동등/부등 조건을 `AND`로 연결한 문법을 지원하며, 지원하지 않는 식은 잘못된 결과를
조용히 반환하지 않고 `InvalidInputException`을 반환합니다.

현재 구현된 control-plane operation 전부(EMR 13개, Glue 22개)는 public Proxy boto3 E2E를
가집니다. 이는 구현 범위 coverage이며 upstream EMR/Glue 전체를 지원한다는 뜻이 아닙니다.
정확한 upstream 분류는 고정된 botocore model에서 생성합니다.

<!-- section: exclusions -->
## 명시적 제외

- AWS Glue Job과 JobRun API
- AWS Glue Crawler
- 미문서화된 AWS 버그 재현
- 기본 local mode의 production IAM authorization 의미론
- EC2/YARN/HDFS 물리적 분산 환경 재현

<!-- section: versions -->
## 버전 기준선

- Python API 서비스: Python 3.11, CI에서 3.11/3.12 검증
- Protocol model: botocore 1.43.66, `contracts/service-model-manifest.json`에서 추적
- Spark: 3.5.x, Glue 상호운용 profile은 Spark 3.5.4
- Java: 17
- Iceberg: Glue 5.0 profile 기준 1.7.1
- AWS SDK for pandas: 3.17.0

Glue 버전은 [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)와 [공식 Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), EMR 의미론은 [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)를 기준으로 합니다.

AWS 문서상 [Data Catalog는 type 문자열을 검증하지 않으므로](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html), Glue type field를 임의로 제한하지 않고 그대로 보존합니다.
