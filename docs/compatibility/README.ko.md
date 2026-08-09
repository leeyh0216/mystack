<!-- doc-id: compatibility-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# 유지보수자용 호환성 참고

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
- [필요한 경우에만 CI 보고서 확인](#필요한-경우에만-ci-보고서-확인)
- [CI가 만드는 검증 자료](#ci가-만드는-검증-자료)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 경로에는 유지보수자가 먼저 읽는 짧은 참고 문서를 둡니다. 상세 검증 보고서는 저장소 문서가 아니라
CI/로컬 빌드 산출물입니다. 지원 API 작업, 테스트 시나리오, 게시 조건을 바꿀 때 이 문서부터 확인합니다.

<!-- section: reading-order -->
## 읽는 순서

1. [Client와 라이브러리 호환성](client-matrix.ko.md) — 지원 클라이언트, 정확한 version, 검증한 세로 흐름
2. [API 호환성 범위](api-coverage.ko.md) — 구현 API 작업과 지원 상태 의미
3. [지원 범위](../support-scope.ko.md) — 제품 약속과 제외 항목
4. [Glue 오류 결정](../protocols/glue/glue-error-decisions.ko.md) — 모델 오류와 우선순위

## 필요한 경우에만 CI 보고서 확인

클라이언트를 실행하거나 지원 범위를 이해하는 데 CI 보고서를 읽을 필요는 없습니다. 유지보수 질문은
아래 문서부터 확인하고, 원본과 테스트만으로 답을 찾을 수 없을 때만 작업 산출물을 확인합니다.

| 질문 | 먼저 볼 문서 | 필요할 때 보는 CI 상세 |
| --- | --- | --- |
| 내 클라이언트 경로를 사용할 수 있는가? | [클라이언트와 라이브러리 호환성](client-matrix.ko.md) | 호환성 사례 보고서 |
| 특정 EMR 또는 Glue API 작업이 구현됐는가? | [API 호환성 범위](api-coverage.ko.md) | 전체 API 분류 |
| Glue 요청이 이 오류를 반환하는 이유는? | [Glue 오류 결정](../protocols/glue/glue-error-decisions.ko.md) | 오류 판단 보고서 |
| 게시 전에 무엇이 통과해야 하는가? | [지원 범위](../support-scope.ko.md) | 게시 수용 보고서 |

<!-- section: generated-artifacts -->
## CI가 만드는 검증 자료

CI는 재현 가능한 파일을 무시되는 `ci-artifacts/compatibility/` 아래에 만듭니다. 필요하면 작업 실행
결과에 첨부하지만, 저장소에 커밋하거나 직접 수정하지 않습니다.

| 보고서 | 필요한 이유 | 사용하는 곳 |
| --- | --- | --- |
| 클라이언트 호환성 표 | CI가 선택한 정확한 테스트/클라이언트/실행 환경 조합 | CI 매트릭스와 게시 검토 |
| 주석 보고서 | 테스트가 검증하는 API 작업과 시나리오 연결 | CI 수집과 유지보수 |
| API 범위 | 고정 botocore 전체 목록과 분류 | 모델 변경 확인 |
| Glue 오류 | 모델 오류와 우선순위 전체 표 | 오류 계약 확인 |
| 게시 수용 범위 | 게시 전에 필요한 호환성 사례 | 게시 확인 절차 |

원본 정책은 `contracts/`에 있고 테스트가 검증 내용을 선언합니다. 생성은 결정적이며 CI는 필수
호환성 사례를 선택하기 전에 실행합니다. 개발자는 보통 `make compatibility-check`로 원본과 산출물의
차이를 확인하며 보고서를 직접 고치지 않습니다.

원본 기준 파일과 변경 뒤 실행할 명령은
[`contracts/README.md`](../../contracts/README.md)에 정리했습니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
