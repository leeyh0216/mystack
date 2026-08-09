<!-- doc-id: evolution -->
<!-- lang: ko -->

[한국어](evolution.ko.md) | [English](evolution.md)

# 상위 구성 요소 변경 대응 정책

<!-- toc:start -->
## 목차

- [변경 격리](#변경-격리)
- [탐지와 대응](#탐지와-대응)
- [Client 또는 runtime version 추가](#client-또는-runtime-version-추가)
- [호환성 변경 체크리스트](#호환성-변경-체크리스트)
<!-- toc:end -->

Mystack은 botocore, AWS protocol, Spark, Hive, Iceberg, Java, Python, container base가 서로 독립적으로 발전하는 upstream 계약이라고 봅니다.

<!-- section: isolation -->
## 변경 격리

- wire metadata/serialization 변경은 `shared/src/mystack/aws_protocol`에서 처리합니다.
- EMR/Glue 작업의 요청·응답 구조나 의미 변경은 해당 서비스 입력 adapter와 사용 사례에서 처리합니다.
- Spark/Hive/Iceberg 변경은 versioned runtime profile과 adapter에서 처리합니다.
- 새 Proxy 서비스는 선언형 route 설정으로 추가하며 분기 코드를 하드코딩하지 않습니다.

<!-- section: detection -->
## 탐지와 대응

1. 주간 workflow가 최신 botocore를 설치하고 commit된 contract manifest와 비교합니다.
2. 보고서는 metadata 변경과 추가·삭제·데이터 구조 변경 작업을 구분합니다.
3. CI 로그는 고정 버전과 현재 버전, 모델 지문, 작업, 입력 구조, `fix_hint`를 포함합니다.
4. Dependabot은 AWS SDK 업데이트를 묶어 protocol 변경을 함께 검토하게 합니다.
5. runtime 업그레이드는 새 matrix entry와 boto3/Spark/Hive/Iceberg E2E 증거가 필요합니다.

<!-- section: manifest -->
## Client 또는 runtime version 추가

1. `tests/support/compatibility_profiles.py`에서 `CompatibilityProfile`을 만들거나 재사용합니다.
   정확한 client version, runtime, lane, GitHub Actions 바깥 job 시간 상한, 공식 URL을 기록합니다.
2. 실제 client 동작을 검증하는 가장 작은 `contract` 또는 `e2e` 시험에
   `@compatibility_evidence(...)`를 붙입니다. scenario, operation, capability, support 값은
   계획한 기능이 아니라 실행하는 test body를 설명해야 합니다.
3. `make compatibility-evidence-generate`를 실행하고 생성한 JSON과 한·영 표를 검토합니다.
   Generator는 [pytest collection](https://docs.pytest.org/en/stable/how-to/usage.html)을 사용하므로
   test body를 실행하지 않고 정확한 node ID를 결정합니다.
4. `make compatibility-evidence-check`와 `make compatibility-case CASE=<id>`를 실행합니다.
   GitHub Actions는 workflow source를 고치지 않아도 생성한 `include` entry에서 독립 job을 만듭니다.
5. `make compatibility-check`는 typed pytest annotation과 생성된
   `contracts/api-coverage.generated.json`을 검증합니다.
   독립된 Glue 오류 조건 정책을 바꾸지 않습니다.

Annotation compiler는 잘못된 marker 구조, 없거나 맞지 않는 실행 marker, 중복 profile, lock/runtime
차이, 알 수 없는 modeled operation, 빠진 API 근거, 변경된 기존 case 선택을 실행 전에 거부합니다.
Case는 정확한 version, scenario/operation ID, model fingerprint, 결정적 evidence hash를 기록하므로
log에서 깨진 경계를 찾을 수 있습니다.
`tests.compatibility_collection_timeout_seconds`가 그 collection subprocess를 제한하며 profile의
duration은 pytest timeout이 아닙니다.

<!-- section: checklist -->
## 호환성 변경 체크리스트

- 직접적인 공식 출처를 링크합니다.
- 한글·영문 문서를 함께 갱신합니다.
- manifest와 coverage를 의도적으로 갱신합니다.
- 정상과 modeled error 계약을 추가합니다.
- 새 side effect 경계에 전/후/오류 로그를 추가합니다.
- 호환성에 필요하면 이전 runtime profile을 보존합니다.

공식 참고 자료: [botocore 모델](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot 설정](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS Hexagonal architecture 변경 대응](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
