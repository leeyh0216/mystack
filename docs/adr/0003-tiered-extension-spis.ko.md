<!-- doc-id: adr-0003-tiered-extension-spis -->
<!-- lang: ko -->

[한국어](0003-tiered-extension-spis.ko.md) | [English](0003-tiered-extension-spis.md)

# ADR 0003: 권한별 프로세스 내부 확장 SPI

- 상태: 승인
- 일자: 2026-08-08

<!-- section: context -->
## 배경

작업 handler가 요청 본문과 다음 handler만 받으면 Mystack이 관리하는 Catalog 상태를
조회할 수 없습니다. 반대로 concrete repository를 모든 확장에 제공하면 application의
불변 조건을 우회할 수 있습니다. 내부 구현이 바뀔 때마다 모든 사용자 확장이 함께
깨질 수도 있습니다.

Python은 설치된 배포 패키지가 선언한 entry point를
[`importlib.metadata.entry_points`](https://docs.python.org/3/library/importlib.metadata.html#entry-points)로
찾을 수 있습니다. PyPA는 [plugin 탐색
안내](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)와
[entry point 명세](https://packaging.python.org/en/latest/specifications/entry-points/)에서
이 방식을 설명합니다.

<!-- section: decision -->
## 결정

공통 비동기 작업 chain 위에 권한과 호환성 계약이 다른 세 SPI를 제공합니다.

| SPI | 주입 객체 | 변경 경로 | 호환성 약속 |
| --- | --- | --- | --- |
| `stable` | 변경할 수 없는 Catalog snapshot과 capability facade | application use case | SPI 주 버전 안에서 유지 |
| `application` | `CatalogApplication`과 공개 domain type | application service 직접 호출 | Mystack 부 버전 단위 |
| `unsafe` | application, repository, clock, 설정 | concrete object 직접 호출 | 정확한 Mystack 버전만 |

각 SPI는 별도 entry-point namespace와 provider `Protocol`을 가집니다. Provider는
composition root에서 context를 한 번 주입받고 operation middleware를 반환합니다. 하위
domain과 application module은 provider나 plugin 구현을 import하지 않습니다. 이 방향은
[AWS Hexagonal architecture
지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을
따릅니다.

<!-- section: execution -->
## 실행 계약

- Middleware는 요청과 다음 handler를 받습니다. 다음 handler를 호출하지 않으면 기존
  동작을 교체합니다.
- 다음 handler 전후에 동작하거나 service error를 잡아서 바꿀 수 있습니다.
- 같은 middleware는 다음 handler를 최대 한 번 호출할 수 있습니다.
- 설정의 우선순위와 ID가 실행 순서를 결정합니다.
- 각 호출에는 설정 가능한 제한 시간을 적용합니다.
- 시작 시 entry point, SPI API 버전, 작업 이름, 중복 ID, `application` 부 버전,
  `unsafe` 허용 여부와 정확한 버전을 검증합니다.
- 확장의 전·후·실패 로그에는 SPI, 확장 ID, 작업, 제한 시간, 수정 안내를 남깁니다.
  요청 본문 값과 인증 정보는 남기지 않습니다.

`application` provider에는 현재 설치의 `major.minor`를 적어야 합니다. `unsafe`는 프로세스
격리나 복구를 제공하지 않습니다. 설정에서 전역 허용을 켜고 provider에 정확한 Mystack
버전을 적어야 로드됩니다.

<!-- section: packaging -->
## 패키징과 Docker

사용자는 entry point를 선언한 wheel을 읽기 전용 directory에 mount합니다. Glue container의
시작 단계는 설정된 directory의 wheel을 별도 설치 directory에 설치합니다. Mystack 기본
환경의 의존성을 바꾸지 않도록 dependency 자동 설치는 허용하지 않습니다. Plugin이 필요한
dependency wheel도 같은 directory에 명시적으로 제공해야 합니다.

확장을 사용하지 않을 때는 설치와 entry-point 탐색을 건너뜁니다. 기본 handler chain과
공개 AWS 동작은 변경되지 않습니다.

<!-- section: consequences -->
## 결과

- 일반적인 오류 보완은 `stable`에서 상태를 조회하고 service error만 바꿀 수 있습니다.
- 더 깊은 domain 동작은 `application`에서 구현할 수 있습니다.
- 실험이나 긴급 복구는 `unsafe`에서 가능하지만 업그레이드 책임은 plugin 작성자에게
  있습니다.
- 세 SPI가 공통 chain을 사용하므로 전처리, 후처리, 오류 전용, 완전 교체 동작을 중복
  구현하지 않습니다.
- 원격 sidecar와 프로세스 격리는 이 결정의 범위가 아닙니다.

<!-- section: alternatives -->
## 검토한 대안

- 요청 본문만 받는 handler는 관리 상태에 접근할 수 없어 제외했습니다.
- concrete repository만 공개하는 단일 SPI는 불변 조건과 장기 호환성을 함께 잃으므로
  제외했습니다.
- 전역 service locator는 의존성이 숨고 시험 격리가 어려워 제외했습니다.

<!-- section: sources -->
## 공식 참고 자료

- [Python entry point 탐색](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [PyPA plugin 탐색 안내](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [PyPA entry point 명세](https://packaging.python.org/en/latest/specifications/entry-points/)
- [AWS Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
