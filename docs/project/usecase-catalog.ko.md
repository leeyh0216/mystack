# 구현 기반 UseCase 카탈로그

한국어 | [English](usecase-catalog.md)

## Metadata와 근거 정책

- 상태: 승인됨, 지속 갱신
- 근거 우선순위: 코드 > 테스트 > commit/issue > 설계 문서
- 공식 protocol 목록: [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data)

## UC-001: AWS 요청 라우팅

- Actor: AWS CLI, boto3, 기타 AWS SDK
- Trigger: public Proxy endpoint HTTP 요청
- Input: method, path/query, byte body, header, YAML route registry
- 검증: route name과 target/signing/host claim의 유일성
- Output: EMR, Glue, LocalStack backend의 byte response
- Side effect: outbound HTTP 요청 1회
- 규칙: target prefix, SigV4 signing name, host prefix, fallback 순서; signed body 재직렬화 금지
- 실패: 시작 시 잘못된 route 설정, 요청 시 backend 연결/timeout
- 관측: route 근거, backend origin, payload byte/fingerprint, status, duration
- 근거: `proxy/src/mystack_proxy/routing.py`, `forwarder.py`, `proxy/tests`
- 신뢰도: High

## UC-002: AWS JSON 1.1 operation 처리

- Actor: EMR 또는 Glue inbound adapter
- Trigger: `X-Amz-Target`을 가진 POST 요청
- Input: service model, target header, JSON object, SigV4 metadata
- 검증: 공식 model의 required/type/enum/constraint
- Output: HTTP 200 modeled JSON 또는 SDK 호환 modeled error
- Side effect: 등록된 application use case 1회 dispatch
- 실패: unknown target, serialization, invalid input, domain service error, internal error
- 관측: service/API/model fingerprint, operation/input shape, request ID, fix hint
- 근거: `shared/src/mystack_aws_protocol/endpoint.py`, `model.py`, `shared/tests`
- 신뢰도: High

## UC-003: Process thread/task stack 진단

- Actor: local 운영자 또는 관리 UI
- Trigger: GET `/_mystack/diagnostics/threads` 또는 `/tasks`
- Input: 선택적 Bearer management token과 stack limit 설정
- Output: thread/task metadata와 source stack line; frame locals 제외
- Side effect: 진단 접근 audit log
- 실패: diagnostics disabled 또는 invalid token
- 근거: `shared/src/mystack_aws_protocol/diagnostics.py`
- 신뢰도: High

## 후보 Gap

- EMR cluster/Step lifecycle과 전체 boto3 control-plane 계약
- LocalStack S3를 통한 EMR bootstrap과 실제 Spark 3.5.x local 실행
- Glue Data Catalog database/table/version/partition/UDF 의미와 오류
- Hive/Iceberg Spark 상호운용
- Docker E2E와 AWS Console 스타일 UI

Glue Job, JobRun, Crawler는 명시적으로 계획하지 않습니다. [지원 범위](../support-scope.ko.md)와 [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)를 참고하세요.

