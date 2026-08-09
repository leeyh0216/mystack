<!-- doc-id: compatibility-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# 유지보수자용 호환성 참고

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
- [필요한 경우에만 생성 보고서 사용](#필요한-경우에만-생성-보고서-사용)
- [CI가 만드는 파일](#ci가-만드는-파일)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 경로는 사람이 먼저 읽을 짧은 문서와 CI가 만드는 상세 증적을 분리합니다. 지원 operation, test
scenario, release 확인 절차를 바꾸는 경우에만 생성 보고서를 확인합니다.

<!-- section: reading-order -->
## 읽는 순서

1. [Client와 라이브러리 호환성](client-matrix.ko.md) — 지원 client, 정확한 version, 검증한 세로 흐름
2. [API 호환성 범위](api-coverage.ko.md) — 구현 operation과 지원 상태 의미
3. [지원 범위](../support-scope.ko.md) — 제품 약속과 제외 항목
4. [Glue 오류 결정](../protocols/glue/glue-error-decisions.ko.md) — 모델 오류와 우선순위

## 필요한 경우에만 생성 보고서 사용

Client를 실행하거나 지원 범위를 이해하는 데 생성 표를 모두 읽을 필요는 없습니다. 유지보수 질문에
맞는 경우에만 아래 상세 보고서를 확인합니다.

| 질문 | 먼저 볼 문서 | 필요할 때 보는 생성 상세 |
| --- | --- | --- |
| 내 client 경로를 사용할 수 있는가? | [Client와 라이브러리 호환성](client-matrix.ko.md) | Client matrix와 annotation evidence |
| 특정 EMR 또는 Glue operation이 구현됐는가? | [API 호환성 범위](api-coverage.ko.md) | 전체 API coverage 표 |
| Glue 요청이 이 오류를 반환하는 이유는? | [Glue 오류 결정](../protocols/glue/glue-error-decisions.ko.md) | Glue 오류 표 |
| 게시 전에 무엇이 통과해야 하는가? | [지원 범위](../support-scope.ko.md) | Release acceptance 보고서 |

<!-- section: generated-artifacts -->
## CI가 만드는 파일

`*.generated.*` 파일은 주 문서가 아니라 상세 감사 결과입니다.

| 산출물 | 필요한 이유 | 사용하는 곳 |
| --- | --- | --- |
| Client matrix | CI가 선택한 정확한 test/client/runtime 조합 | CI matrix와 release 검토 |
| Annotation evidence | test가 증명하는 operation과 scenario 연결 | CI 수집과 유지보수 |
| API coverage | 고정 botocore 전체 목록과 분류 | 모델 드리프트 확인 |
| Glue errors | 모델 오류와 우선순위 전체 표 | 오류 계약 확인 |
| Release acceptance | 게시 전에 필요한 호환성 case | release 확인 절차 |

원천 정책은 `contracts/`에 있고 test가 증거를 선언합니다. 생성은 결정적이며 CI가 필수 case 전에
검증합니다. 개발자는 보통 `make compatibility-check`로 차이를 확인하며 생성 파일을 직접 고치지 않습니다.

원본 기준 파일, 각 생성 기준선의 생산자, 변경 뒤 실행할 명령은
[`contracts/README.md`](../../contracts/README.md)에 정리했습니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
