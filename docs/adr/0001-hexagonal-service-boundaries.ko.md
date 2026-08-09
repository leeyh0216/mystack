<!-- doc-id: adr-0001-hexagonal-service-boundaries -->
<!-- lang: ko -->

[한국어](0001-hexagonal-service-boundaries.ko.md) | [English](0001-hexagonal-service-boundaries.md)

# ADR 0001: Hexagonal 서비스 경계

<!-- toc:start -->
## 목차

- [배경](#배경)
- [결정](#결정)
- [결과](#결과)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

- 상태: 승인
- 일자: 2026-08-08

<!-- section: context -->
## 배경

Protocol parsing, Domain 동작, Spark 실행, LocalStack, 저장소, UI를 결합하지 않으면서 수백 개 AWS API 작업으로 확장해야 합니다. 하위 모듈은 호출자를 알면 안 됩니다.

<!-- section: decision -->
## 결정

Proxy, EMR, Glue는 독립 배포 가능한 Python 패키지입니다. 각 emulator는 Domain, Application, Adapter, Composition Root를 분리합니다. Port는 이를 사용하는 안쪽 계층에서 선언하고 Adapter가 구현합니다. 공유 코드는 AWS wire protocol과 공통 운영 경계로 제한합니다.

Import는 안쪽 방향만 허용하고 architecture 테스트로 강제합니다.

<!-- section: consequences -->
## 결과

- Domain 상태 머신을 FastAPI, Docker, Spark, LocalStack 없이 테스트할 수 있습니다.
- 저장 어댑터를 교체해도 use case를 변경하지 않습니다.
- AWS request/response mapping은 inbound 어댑터에 머물고 wire dictionary가 Domain으로 유출되지 않습니다.
- 도메인 경계 사이의 비즈니스 개념은 무리하게 공유하지 않습니다. 대신 변환 코드의
  일부 중복을 허용합니다.

<!-- section: sources -->
## 공식 참고 자료

[AWS Prescriptive Guidance: Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
