<!-- doc-id: docs-index -->
<!-- lang: ko -->

[한국어](index.ko.md) | [English](index.md)

# 문서 포털

<!-- section: guides -->
## 안내서

Mystack을 유지보수할 때 다음 순서로 시작하세요.

1. [Docker Compose와 Dev Container 사용 안내](getting-started.ko.md)
2. [개발 환경과 10분 설정](development.ko.md)
3. [설정과 재현 가능한 container](configuration.ko.md)
4. [지원 범위](support-scope.ko.md)
5. [아키텍처](architecture.ko.md), [서비스 경계 ADR](adr/0001-hexagonal-service-boundaries.ko.md),
   [확장 SPI ADR](adr/0003-tiered-extension-spis.ko.md)
6. [AWS JSON protocol 분석](protocols/aws-json-1.1.ko.md)
7. [테스트 전략](testing.ko.md)
8. [Client와 library 호환성](compatibility/client-matrix.ko.md)
9. [기여 안내](../CONTRIBUTING.ko.md)
10. [한국어 기술 문서 작성 기준](korean-writing-style.ko.md)
11. [Glue 확장 SPI](extensions.ko.md)
12. [관찰성과 thread 진단](observability.ko.md)
13. [관리 Console과 Resource API](console.ko.md)
14. [CI와 release 자동화](ci.ko.md)
15. [Private GHCR image 게시](container-release.ko.md)
16. [Upstream 변경 대응 정책](evolution.ko.md)
17. [새 emulator route 추가](extending-proxy.ko.md)
18. [구현 기반 UseCase](project/usecase-catalog.ko.md)

아키텍처와 자동 테스트 정책은 [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)를 따릅니다. 모든 동작 문서는 직접적인 공식 AWS, SDK, Python, Docker, GitHub 출처를 포함해야 합니다.
