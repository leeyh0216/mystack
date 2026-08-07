# ADR 0001: Hexagonal 서비스 경계

한국어 | [English](0001-hexagonal-service-boundaries.md)

- 상태: 승인
- 일자: 2026-08-08

## 배경

Protocol parsing, Domain 동작, Spark 실행, LocalStack, 저장소, UI를 결합하지 않으면서 수백 개 AWS operation으로 확장해야 합니다. 하위 모듈은 호출자를 알면 안 됩니다.

## 결정

Proxy, EMR, Glue는 독립 배포 가능한 Python 패키지입니다. 각 emulator는 Domain, Application, Adapter, Composition Root를 분리합니다. Port는 이를 사용하는 안쪽 계층에서 선언하고 Adapter가 구현합니다. 공유 코드는 AWS wire protocol과 공통 운영 경계로 제한합니다.

Import는 안쪽 방향만 허용하고 architecture test로 강제합니다.

## 결과

- Domain 상태 머신을 FastAPI, Docker, Spark, LocalStack 없이 테스트할 수 있습니다.
- 저장 adapter를 교체해도 use case를 변경하지 않습니다.
- AWS request/response mapping은 inbound adapter에 머물고 wire dictionary가 Domain으로 유출되지 않습니다.
- bounded context 간 business concept은 무리하게 공유하지 않고 mapping code 일부 중복을 허용합니다.

## 공식 참고 자료

[AWS Prescriptive Guidance: Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)

