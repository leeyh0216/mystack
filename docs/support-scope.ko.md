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
| EMR control plane | 부분 구현: boto3로 검증한 13개 operation과 같은 use case를 거치는 versioned startup-file 생성 | EMR public API 광범위 호환 |
| EMR bootstrap/Spark | 세로 경로 구현: 정보 확인을 포함한 신뢰된 root pre-start, 최종 `hadoop` 사용자, S3 bootstrap virtualenv, Python/JAR/dependency materialize, Spark 3.5.4 local S3A write, 취소, gzip Step/local-driver LogUri archive | 더 많은 EMR Step 유형, YARN/executor log와 분산 runtime 정합성 |
| Glue Data Catalog | 부분 구현: boto3로 검증한 database/table/version/partition 22개 operation | UDF를 포함한 나머지 범위 내 Catalog API |
| Spark + Hive + Glue Catalog | 세로 경로 구현: 공식 Glue 5 image, complex type, S3 Parquet E2E | 더 넓은 Hive metadata 의미론 |
| Spark + Iceberg + Glue Catalog | 세로 경로 구현: Iceberg 1.7.1 create/append/read/schema evolution E2E | Partition, transaction, 더 넓은 Iceberg API |
| AWS SDK for pandas | 세로 경로 구현: 3.17.0 partitioned Parquet S3/Glue write/read E2E | 더 넓은 Glue/S3 함수와 추가 client 검증 |
| Web console | 구현: EMR cluster/Step 운영, pause/resume/download와 재시작 복구를 지원하는 live log, Glue database/table/schema/partition 탐색, route/thread/task, keyboard/browser E2E | Spark UI와 History Server link |

관리 console은 `/_mystack/console`에서 제공됩니다. Glue metadata mutation은 직렬화한
candidate-state transaction을 사용합니다. Persistence 실패 시 visible state와 durable state를
모두 유지하고 database/table rename 또는 delete는 하위 table과 partition을 한 commit에
포함합니다. Versioned JSON document는 `glue.state_file`에 저장하며 schema version 1은 다음
mutation에서 migration합니다. 이는 표에 남은 Iceberg table transaction 목표와 구분되는 Glue
Data Catalog metadata transaction 동작입니다. 현재 partition expression evaluator는 따옴표로
감싼 동등/부등 조건을 `AND`로 연결한 문법을 지원하며, 지원하지 않는 식은 잘못된 결과를
조용히 반환하지 않고 `InvalidInputException`을 반환합니다.

현재 구현된 control-plane operation 전부(EMR 13개, Glue 22개)는 public Proxy boto3 E2E를
가집니다. 이는 구현 범위 coverage이며 upstream EMR/Glue 전체를 지원한다는 뜻이 아닙니다.
정확한 upstream 분류는 고정된 botocore model에서 생성합니다.
Startup-file entry는 문서화한 allowlist만 받고 `RunJobFlow` member 이름을 사용하며 EMR process
재시작 후 새 ID로 다시 생성합니다. 자세한 내용은 [시작 클러스터
protocol](protocols/emr-startup-clusters.ko.md)에 있습니다.
신뢰된 pre-start script는 명시적으로 활성화하는 EMR container 경계이며 process 안의 plugin API나
EMR bootstrap action이 아닙니다. 정확한 검사와 제외 범위는 [pre-start
계약](protocols/emr-prestart.ko.md)에 있습니다.

<!-- section: exclusions -->
## 명시적 제외

- AWS Glue Job과 JobRun API
- AWS Glue Crawler
- Process 내부 사용자 extension 또는 plugin API
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
