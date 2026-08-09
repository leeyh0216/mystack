<!-- doc-id: support-scope -->
<!-- lang: ko -->

[한국어](support-scope.ko.md) | [English](support-scope.md)

# 지원 범위

<!-- toc:start -->
## 목차

- [개요](#개요)
- [명시적 제외](#명시적-제외)
- [버전 기준선](#버전-기준선)
<!-- toc:end -->

<!-- section: overview -->
## 개요

사용자용 기능·버전·검증 수준의 간단한 답변은 생성된
[client compatibility matrix](compatibility/client-matrix.generated.md)를 사용합니다. 전체 유지보수자
인벤토리는 별도의 [API coverage reference](compatibility/api-coverage.generated.md)에 있습니다.

이 문서는 현재 구현과 장기 목표를 구분합니다. “목표”는 현재 빌드가 이미 호환된다는 뜻이 아닙니다.

| 영역 | 현재 상태 | 목표 |
| --- | --- | --- |
| 확장형 Proxy registry | 구현·단위 테스트 완료 | Proxy 코드 변경 없이 새 AWS JSON/SigV4 emulator 등록 |
| AWS JSON 1.1 codec/model 검증 | 구현·단위 테스트 완료 | EMR/Glue modeled request/response/error 처리 |
| LocalStack fallback | 구현·단위 테스트 완료 | EMR/Glue 외 요청의 투명 전달 |
| EMR control plane | 부분 구현: boto3로 검증한 13개 operation과 같은 use case를 거치는 versioned startup-file 생성 | EMR public API 광범위 호환 |
| EMR bootstrap/Spark | 세로 경로 구현: 정보 확인을 포함한 신뢰된 root pre-start, 최종 `hadoop` 사용자, S3 bootstrap virtualenv, Python/JAR/dependency materialize, Spark 3.5.4 local S3A write, 취소, gzip Step/local-driver LogUri archive | 더 많은 EMR Step 유형, YARN/executor log와 분산 runtime 정합성 |
| Glue Data Catalog | API 목록 일부 지원: boto3로 검증한 database/table/version/partition/batch/table-optimizer 28개 operation의 결정적 오류와 선택적 timeout/internal injection 완성 | 더 넓은 Data Catalog API 목록 |
| Spark + Hive + Glue Catalog | 검증 완료: 공식 Glue 5 image, complex type, type 기반 pruning, partition DDL/repair, 지원하는 Hive V1 table ALTER metadata 의미론, 구현 operation 전체의 결정적 오류 | 더 넓은 Spark/Hive client variant |
| Spark + Iceberg + Glue Catalog | 세로 경로 구현: Open Table Format create/update 입력, create/read/write/evolution, COW/MOR DML, time travel, branch/tag write, 주요 metadata table, snapshot/maintenance procedure, managed compaction/retention/orphan-file optimizer, rename/drop/추적 file purge, S3 cleanup, 원자적 `VersionId` commit과 concurrent retry | Metadata encryption action, 나머지 option/table과 더 넓은 Iceberg API |
| AWS SDK for pandas | 세로 경로 구현: 3.17.0 partitioned Parquet S3/Glue write/read E2E | 이 client가 사용하는 더 넓은 Glue/S3 함수 |
| Service 소유 Web UI | 구현: React/TypeScript EMR cluster/Step/log UI, Glue database/table/schema/partition explorer, 공통 Tailwind design system, thread/task, keyboard/browser E2E | 실행 중 Spark UI link |

EMR과 Glue는 각각 `/_mystack/ui/`에서 자기 UI를 직접 제공합니다. Proxy의 공개 경로는
`/_mystack/ui/emr/`, `/_mystack/ui/glue/`이며 호환 경로 `/_mystack/console`은 EMR로 redirect합니다.
Glue metadata mutation은 짧고 정규화한 SQLite transaction을 사용합니다. Persistence가 실패하면
mutation 전체를 rollback하며 database/table rename 또는 delete는 하위 table, partition, optimizer와
run history를 원자적으로 포함합니다. `glue.sqlite.database_file`이 유일한 영속 catalog store이고,
검증한 기본값은 WAL이며 `rollback`은 명시적인 개발용 escape hatch입니다. JSON catalog fallback이나
migration은 없습니다. Iceberg table도 같은 transaction에서 원자적
`VersionId`/`metadata_location` compare-and-swap을 적용합니다. Data, manifest, metadata,
snapshot과 retry는 계속 Iceberg가 소유합니다. 자세한 내용은 [Iceberg commit
protocol](protocols/glue-iceberg-commits.ko.md)을 참고하세요.
고정된 partition, schema, sort, identifier 동작은 별도 [Iceberg evolution
protocol](protocols/glue-iceberg-evolution.ko.md)에 기록합니다. 고정된 `INSERT`/`UPDATE`/`DELETE`/`MERGE`
동작과 COW/MOR 근거는 [Iceberg row-level DML protocol](protocols/glue-iceberg-row-level-dml.ko.md)에
있습니다. Time travel, reference, metadata table, snapshot/maintenance procedure, S3 cleanup은
[Iceberg snapshot/reference/procedure protocol](protocols/glue-iceberg-snapshots-refs-procedures.ko.md)에
있습니다. Rename, catalog-only drop, 추적 file purge, 보상 작업, Glue/S3 사이 실패 경계는
[Iceberg lifecycle protocol](protocols/glue-iceberg-lifecycle.ko.md)에 있습니다.
`OpenTableFormatInput`과 `UpdateOpenTableFormatInput`을 통한 service 소유 Iceberg v2 metadata
materialization, S3 보상, catalog CAS는 [Open Table Format 입력
protocol](protocols/glue-open-table-format.ko.md)에 있습니다.
Managed optimizer API, 기본값, scheduling, Spark procedure mapping, 오류, log와 제외 범위는
[table optimizer protocol](protocols/glue-table-optimizers.ko.md)에 고정했습니다.
`GetPartitions`는 type이 있는 key, 우선순위,
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

현재 구현된 control-plane operation 전부(EMR 13개, Glue 28개)는 public Proxy boto3 E2E를
가집니다. 이는 구현 범위 coverage이며 upstream EMR/Glue 전체를 지원한다는 뜻이 아닙니다.
정확한 upstream 분류는 고정된 botocore model에서 생성합니다.
생성된 [release 수용 범위](compatibility/release-acceptance.ko.generated.md)는 이 API/오류 계약과
주석 compatibility test의 정확한 Hive, Iceberg, AWS SDK for pandas, EMR PySpark/S3 scenario를
결합한 release-blocking 기준입니다.
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
- Open Table Format metadata encryption-key action
- EC2/YARN/HDFS 물리적 분산 환경 재현
- Spark History Server

<!-- section: versions -->
## 버전 기준선

- Python API 서비스: Python 3.11
- Protocol model: botocore 1.43.66, `contracts/service-model-manifest.json`에서 추적
- Spark: 3.5.x, Glue 상호운용 profile은 Spark 3.5.4
- Java: 17
- Iceberg: Glue 5.0 profile 기준 1.7.1
- AWS SDK for pandas: 3.17.0

Glue 버전은 [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)와 [공식 Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), EMR 의미론은 [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)를 기준으로 합니다.
게시하는 Glue image는 Spark/Iceberg catalog 경로를 유지하지만 넓은 개발용 base에서 범위 밖인 Job,
Delta, Hudi, Flink, streaming, Redshift asset을 제거합니다. 이 image는 신뢰된 local emulator이며 보안
경계가 아니므로 운영자가 관리하는 Glue dataset만 사용해야 합니다. 만료되는 정확한 scan 판정과
upstream advisory는 [container release 운영](container-release.ko.md)에 정리했습니다.

AWS 문서상 [Data Catalog는 type 문자열을 검증하지 않으므로](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html), Glue type field를 임의로 제한하지 않고 그대로 보존합니다.
