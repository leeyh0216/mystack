<!-- doc-id: api-coverage -->
<!-- lang: ko -->

[한국어](api-coverage.ko.md) | [English](api-coverage.md)

# API 호환성 범위

<!-- toc:start -->
## 목차

- [개요](#개요)
- [정책](#정책)
- [구현된 operation](#구현된-operation)
- [결정적 local 오류 계약](#결정적-local-오류-계약)
<!-- toc:end -->

<!-- section: overview -->
## 개요

호환성은 직접 작성한 operation 목록이 아니라 고정 버전의 공식 botocore 서비스 모델을 기준으로 측정합니다.

| 상태 | 의미 |
| --- | --- |
| `COMPATIBLE` | 전송 구조와 문서화된 의미론을 계약 시험으로 검증 |
| `PARTIAL` | 동작하지만 일부 문서화된 계약이 남음 |
| `PROTOCOL_ONLY` | 대상과 요청 구조만 인식하고 의미 구현은 대기 중 |
| `NOT_PLANNED` | 명시적 범위 제외 |

<!-- section: policy -->
## 정책

- 모든 EMR public API operation은 장기 호환 목표입니다.
- Glue Data Catalog public operation은 호환 목표입니다.
- Glue Job, JobRun, Crawler 계열은 `NOT_PLANNED`입니다.
- 생성된 coverage report는 고정 model 버전을 기록하고 upstream operation에 분류가 없으면 CI를 실패시킵니다.
- operation 완료에는 해당되는 정상, validation, not-found/conflict, pagination, idempotency, 상태 의존 테스트가 필요합니다.

우선 수직 범위:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap action, tag
- Glue Catalog: database, table, table version, partition, batch partition, user-defined function

<!-- section: operations -->
## 구현된 operation

다음 operation은 실제 TCP server를 통한 boto3 black-box contract를 갖습니다. 여기서
“구현”은 모든 선택적 의미 분기가 완성됐다는 뜻은 아닙니다.

| 서비스 | Operation |
| --- | --- |
| EMR | `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, `ListBootstrapActions`, `AddTags`, `RemoveTags`, `SetTerminationProtection`, `SetVisibleToAllUsers` |
| Glue | `CreateDatabase`, `GetDatabase`, `GetDatabases`, `UpdateDatabase`, `DeleteDatabase`, `CreateTable`, `GetTable`, `GetTables`, `UpdateTable`, `DeleteTable`, `GetTableVersion`, `GetTableVersions`, `CreatePartition`, `BatchCreatePartition`, `GetPartition`, `GetPartitions`, `BatchGetPartition`, `UpdatePartition`, `BatchUpdatePartition`, `DeletePartition`, `BatchDeletePartition`, `GetCatalogImportStatus` |

문서화된 Glue conflict도 contract에 포함됩니다. 단건 partition 중복 생성은 HTTP 400
`AlreadyExistsException`, batch operation은 항목별 `ErrorDetail`을 반환합니다. 공식
[Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)와
[Glue exception](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)을 기준으로 합니다.

전체 생성형 표는 [api-coverage.ko.generated.md](api-coverage.ko.generated.md)입니다. botocore
1.43.66의 EMR 65개와 Glue 299개 operation을 모두 포함합니다. Commit된 JSON 기준선은
각 작업의 상태와 데이터 구조 지문을 저장합니다. `--check`는 새로운 상위 작업에
기본 상태를 자동 부여하지 않고 미분류로 보고해 CI를 실패시킵니다. 데이터 구조 변경과 삭제도
adapter, test, 문서 수정 안내와 별도로 보고합니다.

<!-- section: local-errors -->
## 결정적 local 오류 계약

Mystack은 실 AWS 계정의 응답과 비교하지 않습니다. 구현된 operation마다 공식 API 문서와 고정
botocore model에서 문서화된 오류 조건, status, 응답 구조를 기록합니다. 최초 실패 순서가
모호하면 검토한 내부 contract로 정합니다. 상태로 유발되는 오류는 parameterized test data로,
문서화된 service/internal 실패는 설정 기반 fault injection으로 재현합니다. IAM, Lake Formation,
인증, 인가 오류는 호환 목표로 분류하지 않습니다.

공식 작업과 데이터 구조 목록은 [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data), Glue 동작은 [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)를 기준으로 합니다.
