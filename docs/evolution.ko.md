<!-- doc-id: evolution -->
<!-- lang: ko -->

[한국어](evolution.ko.md) | [English](evolution.md)

# 상위 구성 요소 변경 대응 정책

<!-- toc:start -->
## 목차

- [변경 격리](#변경-격리)
- [탐지와 대응](#탐지와-대응)
- [클라이언트 또는 실행 환경 버전 추가](#클라이언트-또는-실행-환경-버전-추가)
- [호환성 변경 체크리스트](#호환성-변경-체크리스트)
<!-- toc:end -->

Mystack은 botocore, AWS 프로토콜, Spark, Hive, Iceberg, Java, Python, 컨테이너 기반 이미지가 서로
독립적으로 발전하는 상위 구성 요소의 계약이라고 봅니다.

<!-- section: isolation -->
## 변경 격리

- 전송 메타데이터/직렬화 변경은 `shared/src/mystack/aws_protocol`에서 처리합니다.
- EMR/Glue API 작업의 요청·응답 구조나 의미 변경은 해당 서비스 입력 어댑터와 사용 사례에서 처리합니다.
- Spark/Hive/Iceberg 변경은 버전별 실행 환경 프로필과 어댑터에서 처리합니다.
- 새 Proxy 서비스는 선언형 경로 설정으로 추가하며 분기 코드를 하드코딩하지 않습니다.

<!-- section: detection -->
## 탐지와 대응

1. 주간 워크플로가 최신 botocore를 설치하고 커밋된 계약 매니페스트와 비교합니다.
2. 보고서는 메타데이터 변경과 추가·삭제·데이터 구조 변경 작업을 구분합니다.
3. CI 로그는 고정 버전과 현재 버전, 모델 지문, 작업, 입력 구조, `fix_hint`를 포함합니다.
4. Dependabot은 AWS SDK 업데이트를 묶어 protocol 변경을 함께 검토하게 합니다.
5. 실행 환경 업그레이드에는 새 호환성 표 항목과 boto3/Spark/Hive/Iceberg E2E 검증이 필요합니다.

<!-- section: manifest -->
## 클라이언트 또는 실행 환경 버전 추가

1. `tests/support/compatibility_profiles.py`에서 `CompatibilityProfile`을 만들거나 재사용합니다.
   정확한 클라이언트 버전, 실행 환경, CI 단계, GitHub Actions 작업 시간 상한, 공식 URL을 기록합니다.
2. 실제 클라이언트 동작을 검증하는 가장 작은 `contract` 또는 `e2e` 테스트에
   `@compatibility_evidence(...)`를 붙입니다. 시나리오, API 작업, 기능, 지원 값은 계획한 기능이
   아니라 실행하는 테스트 본문을 설명해야 합니다.
3. `make compatibility-evidence-generate`를 실행하고 `ci-artifacts/compatibility/`의 CI/로컬
   보고서를 검토합니다. 생성기는 [pytest 수집](https://docs.pytest.org/en/stable/how-to/usage.html)을
   사용하므로 테스트 본문을 실행하지 않고 정확한 노드 ID를 결정합니다.
4. `make compatibility-evidence-check`와 `make compatibility-case CASE=<id>`를 실행합니다.
   GitHub Actions는 워크플로 원본을 고치지 않아도 생성한 `include` 항목에서 독립 작업을 만듭니다.
5. `make compatibility-check`는 형식 지정 pytest 주석과
   `contracts/compatibility-scope-policy.yaml`의 일치 여부를 검증합니다. API 동작 자체를 바꾸지
   않는다면 독립된 Glue 오류 조건 정책은 바꾸지 않습니다.

주석 수집기는 잘못된 표식 구조, 없거나 맞지 않는 실행 표식, 중복 프로필, 잠금 파일/실행 환경
차이, 알 수 없는 모델 API 작업, 누락된 API 검증, 변경된 사례 선택을 실행 전에 거부합니다. 사례는
정확한 버전, 시나리오/API 작업 ID, 모델 지문, 결정적 요약값을 기록하므로 로그에서 문제가 생긴
경계를 찾을 수 있습니다. `tests.compatibility_collection_timeout_seconds`가 수집 하위 프로세스를
제한하며 프로필의 실행 시간은 pytest 제한 시간이 아닙니다.

<!-- section: checklist -->
## 호환성 변경 체크리스트

- 직접적인 공식 출처를 링크합니다.
- 한글·영문 문서를 함께 갱신합니다.
- manifest와 범위를 의도적으로 갱신합니다.
- 정상과 modeled error 계약을 추가합니다.
- 새 side effect 경계에 전/후/오류 로그를 추가합니다.
- 호환성에 필요하면 이전 실행 환경 프로필을 보존합니다.

공식 참고 자료: [botocore 모델](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot 설정](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS Hexagonal architecture 변경 대응](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
