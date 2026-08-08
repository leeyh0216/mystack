<!-- doc-id: adr-0002-versioned-upstream-adapters -->
<!-- lang: ko -->

[한국어](0002-versioned-upstream-adapters.ko.md) | [English](0002-versioned-upstream-adapters.md)

# ADR 0002: 버전별 상위 어댑터와 파일 기반 설정

- 상태: 승인
- 일자: 2026-08-08

<!-- section: context -->
## 배경

AWS protocol, botocore model, Spark, Hive, Iceberg, container base는 서로 독립적으로 발전합니다. Route, endpoint, version, timeout 하드코딩은 업그레이드를 위험하게 만들고 Docker 배포 유연성을 낮춥니다.

<!-- section: decision -->
## 결정

- schema version이 있는 단일 YAML 설정을 commit하고 container에 read-only mount합니다.
- 범용 `MYSTACK__SECTION__KEY` 환경변수 override와 명시적 CLI override를 허용합니다.
- botocore model은 protocol model facade와 commit된 fingerprint manifest 뒤에 격리합니다.
- Spark/Hive/Iceberg 조합은 이름이 있는 runtime profile로 격리합니다.
- 정기 workflow가 upstream model drift를 탐지하고 변경 operation을 정확히 보고합니다.
- 설정 secret 값은 기록하지 않고 source, fingerprint, redacted override path만 기록합니다.

<!-- section: consequences -->
## 결과

- 새 emulator route는 Proxy 코드가 아닌 설정 변경으로 추가합니다.
- 업그레이드는 이름이 있는 adapter/profile과 재현 가능한 E2E 증거를 가집니다.
- 잘못된 설정은 수정할 경로를 포함해 시작 시 실패합니다.
- 설정 schema migration에는 ADR과 한·영 migration note가 필요합니다.

<!-- section: sources -->
## 공식 참고 자료

- [Docker Compose configs](https://docs.docker.com/reference/compose-file/configs/)
- [공식 botocore 모델](https://github.com/boto/botocore/tree/develop/botocore/data)
- [AWS Hexagonal architecture 변경 대응](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
