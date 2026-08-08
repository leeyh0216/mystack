<!-- doc-id: maintainer-guide -->
<!-- lang: ko -->

[한국어](maintainers.ko.md) | [English](maintainers.md)

# 유지보수 안내

이 문서는 Mystack을 구현, 검토, 운영하거나 배포하는 분을 위한 문서 지도입니다. Mystack을
애플리케이션에서 사용하는 방법은 [사용자 안내](index.ko.md)를 먼저 읽으세요.

<!-- section: start -->
## 처음 기여하기

1. [기여 가이드](../CONTRIBUTING.ko.md)에서 branch, issue, commit, review 규칙을 확인합니다.
2. [개발 환경 안내](development.ko.md)로 `direnv`, uv, Dev Container 중 하나를 설정합니다.
3. [프로젝트 기준선](project/baseline.ko.md)과 [구현 기반 UseCase](project/usecase-catalog.ko.md)로
   현재 구현 상태를 확인합니다.
4. `make test`, `make contract`, 필요한 Docker E2E를 명시적 timeout으로 실행합니다.

<!-- section: architecture -->
## Architecture와 의존성

- 전체 component와 dependency 방향: [Architecture](architecture.ko.md)
- 하위 module이 상위 module을 모르게 하는 결정: [ADR-0001](adr/0001-hexagonal-service-boundaries.ko.md)
- Version이 고정된 upstream adapter: [ADR-0002](adr/0002-versioned-upstream-adapters.ko.md)
- 세 수준 Glue extension SPI: [ADR-0003](adr/0003-tiered-extension-spis.ko.md)
- 새 service를 Proxy에 등록: [Proxy 확장 안내](extending-proxy.ko.md)

<!-- section: protocol -->
## Protocol과 호환성

- AWS JSON 1.1 request, response, error와 Iceberg 책임 경계: [Protocol 분석](protocols/aws-json-1.1.ko.md)
- 고정 botocore model과 구현 상태: [API coverage](compatibility/api-coverage.ko.md)
- 외부 client별 E2E claim: [Client 호환성 표](compatibility/client-matrix.ko.md)
- AWS, boto, Spark 변경 대응 위치와 자동 검사: [변경 대응 정책](evolution.ko.md)

Protocol을 변경할 때는 controller만 보지 말고 model manifest, dispatcher, domain error mapping,
public-Proxy contract와 E2E를 같은 issue에서 갱신합니다.

<!-- section: implementation -->
## 구현과 extension

- File-first 설정 schema와 Docker override: [설정 안내](configuration.ko.md)
- Glue SPI package, context, wheel 설치와 보안 경계: [Extension 안내](extensions.ko.md)
- Composition root와 side-effect boundary는 [Architecture](architecture.ko.md)의 log와 dependency
  규칙을 따릅니다.
- 한국어와 영문 문서를 함께 고칠 때는 [한국어 기술 문서 기준](korean-writing-style.ko.md)을
  적용합니다.

<!-- section: quality -->
## Test와 CI

- Unit, architecture, contract, differential, Docker E2E: [Test 전략](testing.ko.md)
- Pull request와 scheduled workflow: [CI 안내](ci.ko.md)
- 모든 test 명령은 `config/mystack.yaml`의 timeout 또는 명시적 `--timeout`을 사용합니다.
- Protocol이나 client 호환성 수정은 최소 unit/contract와 실제 public-Proxy E2E 증거를 함께
  추가합니다.

<!-- section: operations -->
## 관찰성과 release

- Boundary log, secret redaction, thread/task stack: [관찰성 안내](observability.ko.md)
- Resource/log UI와 관리 API: [Console 안내](console.ko.md)
- Private GHCR multi-platform build, tag, SBOM, provenance와 scan: [Container release](container-release.ko.md)

<!-- section: workflow -->
## Issue 단위 작업 흐름

1. 구현 전에 bilingual GitHub issue를 만들고 milestone과 area/type label을 지정합니다.
2. 한 issue의 code, test, user/maintainer 문서를 함께 완성합니다.
3. Local 확인 절차와 필요한 E2E를 통과한 뒤 issue 번호가 있는 하나의 논리적 commit을 만듭니다.
4. Commit을 바로 push하고 CI 결과를 확인한 뒤 issue를 닫습니다.
5. 다음 관심사는 새 issue와 새 commit으로 분리해 완료된 변경을 working tree에 누적하지 않습니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Hexagonal architecture 변경 대응](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
- [GitHub issue와 pull request 연결](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [Docker Compose CI/CD](https://docs.docker.com/compose/how-tos/ci-cd/)
