<!-- doc-id: protocols-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# Protocol 구현 안내

<!-- toc:start -->
## 목차

- [주제별 읽는 순서](#주제별-읽는-순서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 문서는 공개 AWS 호환 API를 뒷받침하는 내부 동작을 설명합니다. 기여자는 service 안내에서 시작한 뒤
변경하려는 경로를 순서대로 읽습니다.

<!-- section: reading-order -->
## 주제별 읽는 순서

### Glue Data Catalog

1. [SQLite runtime](glue-sqlite-runtime.ko.md) — catalog 내구성과 runtime 제약
2. [Database/table 오류](glue-database-table-errors.ko.md), [오류 결정](glue-error-decisions.ko.md)
3. [Partition expression](glue-partition-expressions.ko.md), [batch 오류](glue-partition-batch-errors.ko.md)
4. [Open Table Format](glue-open-table-format.ko.md)
5. Iceberg 확장: [commit](glue-iceberg-commits.ko.md), [evolution](glue-iceberg-evolution.ko.md),
   [row-level DML](glue-iceberg-row-level-dml.ko.md), [snapshot/ref/procedure](glue-iceberg-snapshots-refs-procedures.ko.md),
   [lifecycle](glue-iceberg-lifecycle.ko.md)

### Amazon EMR

1. [Startup cluster](emr-startup-clusters.ko.md)
2. [Pre-start action](emr-prestart.ko.md)
3. [Log layout](emr-log-layout.ko.md)

### 공유 wire protocol

- [AWS JSON 1.1](aws-json-1.1.ko.md)

문서에서 CI 전용 workload를 언급하면 runtime 기능이 아니라 test infrastructure입니다. 해당 source와
scenario 이름은 대응하는 `tests/e2e` case와 함께 변경합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS JSON protocol reference](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.LowLevelAPI.html)
- [Apache Iceberg documentation](https://iceberg.apache.org/docs/latest/)
