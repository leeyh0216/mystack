<!-- doc-id: protocols/glue/glue-error-decisions -->
<!-- lang: ko -->

[한국어](glue-error-decisions.ko.md) | [English](glue-error-decisions.md)

# 결정적인 Glue 오류 판단

<!-- toc:start -->
## 목차

- [판단 우선순위](#판단-우선순위)
- [분류와 wire response](#분류와-wire-response)
- [재현 가능한 failure injection](#재현-가능한-failure-injection)
- [Logging과 유지보수](#logging과-유지보수)
- [제외 범위](#제외-범위)
- [공식 출처](#공식-출처)
<!-- toc:end -->

Mystack은 공개 API 문서, 고정한 botocore model, 내부 catalog invariant로 Glue 오류를 정의하며 실
AWS 계정을 조회하지 않습니다. Source of truth는 `contracts/glue-error-conditions.yaml`입니다.
`scripts/compatibility/glue_error_contracts.py`는 구현한 28개 operation 모두에 순서가 있는 계약을 요구하고
[영문](../../compatibility/glue-errors.generated.md)과
[한글](../../compatibility/glue-errors.ko.generated.md) matrix를 생성합니다.

<!-- section: precedence -->
## 판단 우선순위

처음 실패한 조건에서 다음 순서로 평가를 중단합니다.

1. AWS JSON/공식 operation 요청 구조와 JSON type
2. Model의 필수 field
3. Model의 value constraint
4. 명시적으로 설정한 fault injection
5. Operation별 application constraint와 parent/resource 존재 여부
6. 중복 또는 destination 충돌
7. Version/concurrency 선행 조건
8. Candidate mutation 또는 순서가 있는 batch item 실행
9. Durable persistence side effect

Protocol 검증은 Glue dispatcher 전의 공통 AWS endpoint에서 수행합니다. 유효한 요청은
`GlueErrorBoundary`로 들어가 선택적 fault를 적용하고 framework를 모르는 domain failure를
변환합니다. Repository는 durable save가 성공한 뒤에만 candidate를 공개합니다. Batch item
실패는 response member이므로 앞에서 성공한 item과 함께 존재할 수 있습니다. Operation별 의미론은
[partition/batch 계약](glue-partition-batch-errors.ko.md)에 고정했습니다.

이는 문서화되지 않은 AWS 평가 순서에 대한 주장이 아니라 Mystack 내부의 결정적인 순서입니다.
[Database/table/version 계약](glue-database-table-errors.ko.md)과
[partition/batch 계약](glue-partition-batch-errors.ko.md)이 pipeline을 바꾸지 않고 resource별
조건을 고정합니다.

<!-- section: taxonomy -->
## 분류와 wire response

| Category | 대표 조건 | AWS JSON code | Mutation 보장 |
| --- | --- | --- | --- |
| Validation | `protocol.input_shape`, `input.value_invalid` | `InvalidInputException` | Handler 미호출 또는 candidate 미commit |
| Not found | `resource.not_found` | `EntityNotFoundException` | Candidate 미commit |
| Conflict | `resource.already_exists` | `AlreadyExistsException` | Candidate 미commit |
| Concurrency | `version.mismatch` | `ConcurrentModificationException` | Candidate 미commit |
| Injectable | `fault.operation_timeout`, `fault.internal_service` | 설정한 문서 기반 code | Handler 미호출 |
| System | `adapter.mapping_failure`, `persistence.side_effect_failed` | `InternalServiceException` | Candidate 미commit/미공개 |

공통 AWS JSON 1.1 controller는 `__type`, `Message`, model 기반 HTTP status,
`x-amzn-errortype`, `x-amzn-requestid` 형식 하나로 serialize합니다. Adapter mapping과
persistence message는 정제합니다. 요청 값과 설정한 fault message는 구조화 log에 기록하지
않습니다.

인증, 인가, IAM, Lake Formation, signing 거부, cross-account, cross-Region 판단은 금지합니다.
SigV4 metadata는 routing context에 사용할 수 있지만 security boundary가 아닙니다.

<!-- section: injection -->
## 재현 가능한 failure injection

Fault injection 기본값은 off이며 `glue.fault_injection`에서만 설정합니다. Rule은 `id`, 구현된
`operation`, 문서화된 `error_code`, response `message`를 가집니다. 지원 code는
`OperationTimeoutException`(HTTP 400)과 `InternalServiceException`(HTTP 500)입니다. 중복 rule
ID, 한 operation의 복수 rule, 알 수 없는 operation, 인증·인가 오류는 process 시작을
실패시킵니다.

Injection은 operation 전체에 적용하고 의도적으로 state가 없습니다. 설정을 끄고 process를
재시작할 때까지 모든 유효한 일치 요청이 실패합니다. 숨은 counter, request header, payload 값
matching이 없어 test가 재현 가능합니다. 잘못된 요청 구조는 fault보다 먼저 실패하며 application과
repository side effect는 시작하지 않습니다.

<!-- section: logging -->
## Logging과 유지보수

Operation 수준에서 변환되거나 주입된 오류마다 `glue.error.decision`이 request/operation/family, condition ID,
category, phase, error code, HTTP status, mutation 보장, 안전한 failure type을 기록합니다. 공통
dispatcher와 controller는 model fingerprint, duration, 최종 code를 추가합니다. Fault는 rule ID를
기록하지만 설정한 message는 기록하지 않습니다.

Client upgrade로 깨지면 다음 순서로 확인합니다.

1. `protocol.validation.failed`: 고정한 botocore input model 변경입니다. 공통 요청 구조 지원 또는
   operation mapping을 수정합니다.
2. `adapter.mapping_failure`: model을 통과한 요청이 오래된 inbound family에 도달했습니다.
   Repository가 아니라 해당 family를 수정합니다.
3. Domain condition: application invariant 또는 error catalog row 변경입니다.
4. `persistence.side_effect_failed`: repository transaction 전후 log와 mounted state path를
   확인합니다.
5. Generated drift: 검토할 operation과 condition을 식별합니다.

의도적으로 catalog를 바꾼 뒤 `make glue-errors-generate`, 로컬/CI 검증에는
`make glue-errors-check`를 사용합니다.

<!-- section: exclusions -->
## 제외 범위

문서화되지 않은 service bug를 재현하거나 실 AWS와 비교하거나 부분 disk corruption 또는
확률·latency 기반 chaos를 주입하지 않습니다. Glue Job과 Crawler는 구현 operation이 아니므로
rule에서 선택할 수 없습니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue exception](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)
- [AWS Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [botocore Glue service model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
- [AWS JSON 1.1 protocol 예제](https://docs.aws.amazon.com/singlesignon/latest/OIDCAPIReference/Welcome.html)
