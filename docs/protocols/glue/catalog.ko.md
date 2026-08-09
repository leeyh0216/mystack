<!-- doc-id: glue-catalog-guide -->
<!-- lang: ko -->

[한국어](catalog.ko.md) | [English](catalog.md)

# Glue Catalog 안내

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 안내는 공개 API 뒤의 지속적인 Glue Data Catalog 동작을 묶습니다.

<!-- section: reading-order -->
## 읽는 순서

1. [SQLite runtime](glue-sqlite-runtime.ko.md) — 저장소 보장과 실행 환경 한계
2. [Database와 table 오류](glue-database-table-errors.ko.md) — 카탈로그 유효성 검사과 실패
3. [오류 결정](glue-error-decisions.ko.md) — 결정적인 최초 실패 우선순위
4. [Partition expression](glue-partition-expressions.ko.md) — parser와 type 기반 filter 동작
5. [Batch partition 오류](glue-partition-batch-errors.ko.md) — 항목별 partial-success 의미론
6. [Table optimizer](glue-table-optimizers.ko.md) — 지원하는 optimizer control-plane 동작

Catalog API 변경에는 `glue/tests/`의 boto3 계약를 사용합니다. 전체 공개 지원 주장은
[`docs/compatibility/api-coverage.ko.md`](../../compatibility/api-coverage.ko.md)에 요약합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue Data Catalog API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
