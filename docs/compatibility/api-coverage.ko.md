<!-- doc-id: api-coverage -->
<!-- lang: ko -->

[한국어](api-coverage.ko.md) | [English](api-coverage.md)

# API 호환성 범위

<!-- toc:start -->
## 목차

- [개요](#개요)
- [정책](#정책)
- [현재 구현한 API 작업](#현재-구현한-api-작업)
- [결정적인 로컬 오류 계약](#결정적인-로컬-오류-계약)
<!-- toc:end -->

<!-- section: overview -->
## 개요

호환성은 직접 작성한 API 작업 목록이 아니라 고정 버전의 공식 botocore 서비스 모델을 기준으로
측정합니다. 서비스별 API 목록은 [Amazon EMR API 작업](https://docs.aws.amazon.com/emr/latest/APIReference/API_Operations.html)과
[AWS Glue Web API 작업](https://docs.aws.amazon.com/glue/latest/webapi/API_Operations.html)입니다.

| 상태 | 의미 |
| --- | --- |
| `COMPATIBLE` | 전송 구조와 문서화된 의미론을 계약 시험으로 검증 |
| `PARTIAL` | 동작하지만 일부 문서화된 계약이 남음 |
| `PROTOCOL_ONLY` | 대상과 요청 구조만 인식하고 의미 구현은 대기 중 |
| `NOT_PLANNED` | 명시적 범위 제외 |

<!-- section: policy -->
## 정책

- 모든 EMR 공개 API 작업은 장기 호환 목표입니다.
- Glue Data Catalog 공개 API 작업은 호환 목표입니다.
- Glue Job, JobRun, Crawler 계열은 `NOT_PLANNED`입니다.
- CI 보고서는 고정 모델 버전을 기록하고 상위 API 작업에 분류가 없으면 CI를 실패시킵니다.
- API 작업 완료에는 해당되는 정상, 유효성 검사, 없음/충돌, 페이지 나누기, 멱등성, 상태 의존 테스트가 필요합니다.

우선 수직 범위:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap action, tag
- Glue Catalog: database, table, table version, partition, batch partition, table optimizer

<!-- section: operations -->
## 현재 구현한 API 작업

다음 API 작업은 실제 TCP 서버를 통한 boto3 블랙박스 계약을 갖습니다. 여기서
“구현”은 모든 선택적 의미 분기가 완성됐다는 뜻은 아닙니다.

| 서비스 | API 작업 |
| --- | --- |
| EMR | `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, `ListBootstrapActions`, `AddTags`, `RemoveTags`, `SetTerminationProtection`, `SetVisibleToAllUsers` |
| Glue database와 table | `CreateDatabase`, `GetDatabase`, `GetDatabases`, `UpdateDatabase`, `DeleteDatabase`, `CreateTable`, `GetTable`, `GetTables`, `UpdateTable`, `DeleteTable`, `GetTableVersion`, `GetTableVersions`, `GetCatalogImportStatus` |
| Glue partition | `CreatePartition`, `BatchCreatePartition`, `GetPartition`, `GetPartitions`, `BatchGetPartition`, `UpdatePartition`, `BatchUpdatePartition`, `DeletePartition`, `BatchDeletePartition` |
| Glue table optimizer | `CreateTableOptimizer`, `GetTableOptimizer`, `BatchGetTableOptimizer`, `UpdateTableOptimizer`, `DeleteTableOptimizer`, `ListTableOptimizerRuns` |

문서화된 Glue 충돌도 계약에 포함됩니다. 단건 파티션 중복 생성은 HTTP 400
`AlreadyExistsException`, 일괄 API 작업은 항목별 `ErrorDetail`을 반환합니다. 공식
[Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)와
[Glue exception](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)을 기준으로 합니다.

CI는 전체 분류를 `ci-artifacts/compatibility/api-coverage.ko.md`에 만듭니다. 이 파일은 고정한
botocore 1.43.66 모델의 모든 공식 API 작업을 분류하는 CI 보고서이며, 저장소에 커밋하는 참고 문서가
아닙니다. `PROTOCOL_ONLY`는 호출 가능한 지원이 아니라 상위 요청/응답 모델만 추적한다는 뜻입니다.
새롭거나 변경된 상위 API 작업은 구현 결정, 테스트, 문서가 일치할 때까지 미분류로 보고되어 CI를
실패시킵니다.

<!-- section: local-errors -->
## 결정적인 로컬 오류 계약

Mystack은 실제 AWS 계정의 응답과 비교하지 않습니다. 구현된 API 작업마다 공식 API 문서와 고정
botocore 모델에서 문서화된 오류 조건, 상태, 응답 구조를 기록합니다. 최초 실패 순서가 모호하면
검토한 내부 계약으로 정합니다. 상태로 유발되는 오류는 매개변수화한 테스트 데이터로, 문서화된
서비스/내부 실패는 설정 기반 장애 주입으로 재현합니다. IAM, Lake Formation,
인증, 인가 오류는 호환 목표로 분류하지 않습니다.

공식 작업과 데이터 구조 목록은 [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data), Glue 동작은 [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), EMR 동작은 [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)를 기준으로 합니다.
