# API 호환성 범위

한국어 | [English](api-coverage.md)

호환성은 직접 작성한 operation 목록이 아니라 고정 버전의 공식 botocore 서비스 모델을 기준으로 측정합니다.

| 상태 | 의미 |
| --- | --- |
| `COMPATIBLE` | wire shape와 문서화된 의미론을 contract test로 검증 |
| `PARTIAL` | 동작하지만 일부 문서화된 계약이 남음 |
| `PROTOCOL_ONLY` | target/shape만 인식하고 의미 구현은 대기 중 |
| `NOT_PLANNED` | 명시적 범위 제외 |

## 정책

- 모든 EMR public API operation은 장기 호환 목표입니다.
- Glue Data Catalog public operation은 호환 목표입니다.
- Glue Job, JobRun, Crawler 계열은 `NOT_PLANNED`입니다.
- 생성된 coverage report는 고정 model 버전을 기록하고 upstream operation에 분류가 없으면 CI를 실패시킵니다.
- operation 완료에는 해당되는 정상, validation, not-found/conflict, pagination, idempotency, 상태 의존 테스트가 필요합니다.

우선 수직 범위:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap action, tag
- Glue Catalog: database, table, table version, partition, batch partition, user-defined function

공식 operation/shape 목록은 [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data), Glue 동작은 [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)를 기준으로 합니다.

