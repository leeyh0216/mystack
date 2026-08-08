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
| Glue Data Catalog | API 목록 일부 지원: boto3로 검증한 22개 operation의 database/table/version/partition/batch 결정적 오류와 선택적 timeout/internal injection 완성 | 더 넓은 Data Catalog API 목록 |
| Spark + Hive + Glue Catalog | 검증 완료: 공식 Glue 5 image, complex type, type 기반 pruning, partition DDL/repair, 지원하는 Hive V1 table ALTER metadata 의미론, 구현 operation 전체의 결정적 오류 | 더 넓은 Spark/Hive client variant |
| Spark + Iceberg + Glue Catalog | 세로 경로 구현: Iceberg 1.7.1 create/append/read, hidden partition/schema/sort/identifier evolution, 원자적 `VersionId` pointer commit과 concurrent-writer retry E2E | Row-level DML, snapshot/ref/procedure, lifecycle operation과 더 넓은 Iceberg API |
| AWS SDK for pandas | 세로 경로 구현: 3.17.0 partitioned Parquet S3/Glue write/read E2E | 이 client가 사용하는 더 넓은 Glue/S3 함수 |
| Service 소유 Web UI | 구현: React/TypeScript EMR cluster/Step/log UI, Glue database/table/schema/partition explorer, 공통 Tailwind design system, thread/task, keyboard/browser E2E | 실행 중 Spark UI link |

EMR과 Glue는 각각 `/_mystack/ui/`에서 자기 UI를 직접 제공합니다. Proxy의 공개 경로는
`/_mystack/ui/emr/`, `/_mystack/ui/glue/`이며 호환 경로 `/_mystack/console`은 EMR로 redirect합니다.
Glue metadata mutation은 직렬화한
candidate-state transaction을 사용합니다. Persistence 실패 시 visible state와 durable state를
모두 유지하고 database/table rename 또는 delete는 하위 table과 partition을 한 commit에
포함합니다. Versioned JSON document는 `glue.state_file`에 저장하며 schema version 1은 다음
mutation에서 migration합니다. Iceberg table에서는 process 간 file lock, 최신 state reload,
원자적 `VersionId`/`metadata_location` compare-and-swap도 적용합니다. Data, manifest, metadata,
snapshot과 retry는 계속 Iceberg가 소유합니다. 자세한 내용은 [Iceberg commit
protocol](protocols/glue-iceberg-commits.ko.md)을 참고하세요.
고정된 partition, schema, sort, identifier 동작은 별도 [Iceberg evolution
protocol](protocols/glue-iceberg-evolution.ko.md)에 기록합니다. `GetPartitions`는 type이 있는 key, 우선순위,
pagination, segment와 함께 문서화된 비교·논리·`IN`·`BETWEEN`·`LIKE`·null predicate를
지원합니다. 문법과 limit은 [partition expression
protocol](protocols/glue-partition-expressions.ko.md)을 참고하세요.
Spark Hive partition add/drop/rename/location과 repair mapping은 [Hive partition DDL
protocol](protocols/glue-hive-partition-ddl.ko.md)에 정리했습니다.
지원하는 table-level column/property/SerDe/location 변경과 client가 거부하는 variant는 [Hive
table ALTER protocol](protocols/glue-hive-table-alter.ko.md)에 정리했습니다.
구현한 모든 operation은 생성한 [Glue 오류
matrix](compatibility/glue-errors.ko.generated.md)에 포함됩니다. 우선순위, 안전한 logging, file 기반
failure injection은 [오류 결정 protocol](protocols/glue-error-decisions.ko.md)에 정의했습니다.
Database/table/version의 validation, conflict, version, archive, rename, cascade, rollback은
[resource 오류 계약](protocols/glue-database-table-errors.ko.md)에 고정했습니다.
Partition value, 목록, update, batch 순서, 항목 오류, `UnprocessedKeys`, rollback은
[partition/batch 오류 계약](protocols/glue-partition-batch-errors.ko.md)에 고정했습니다.

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
- 인증, 인가, IAM, Lake Formation 의미론
- Cross-account와 cross-Region 의미론
- 실 AWS 비교 test와 cloud credential
- PyIceberg, Flink, Trino, Glue Iceberg REST endpoint
- EC2/YARN/HDFS 물리적 분산 환경 재현
- Spark History Server

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
