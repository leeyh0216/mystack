<!-- doc-id: compatibility-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# 유지보수자용 호환성 참고

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
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
4. [Glue 오류 결정](../protocols/glue-error-decisions.ko.md) — 모델 오류와 우선순위

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

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
