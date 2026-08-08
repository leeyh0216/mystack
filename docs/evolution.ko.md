<!-- doc-id: evolution -->
<!-- lang: ko -->

[한국어](evolution.ko.md) | [English](evolution.md)

# 상위 구성 요소 변경 대응 정책

Mystack은 botocore, AWS protocol, Spark, Hive, Iceberg, Java, Python, container base가 서로 독립적으로 발전하는 upstream 계약이라고 봅니다.

<!-- section: isolation -->
## 변경 격리

- wire metadata/serialization 변경은 `shared/src/mystack_aws_protocol`에서 처리합니다.
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

<!-- section: checklist -->
## 호환성 변경 체크리스트

- 직접적인 공식 출처를 링크합니다.
- 한글·영문 문서를 함께 갱신합니다.
- manifest와 coverage를 의도적으로 갱신합니다.
- 정상과 modeled error 계약을 추가합니다.
- 새 side effect 경계에 전/후/오류 로그를 추가합니다.
- 호환성에 필요하면 이전 runtime profile을 보존합니다.

공식 참고 자료: [botocore 모델](https://github.com/boto/botocore/tree/develop/botocore/data), [GitHub Dependabot 설정](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates), [AWS Hexagonal architecture 변경 대응](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
