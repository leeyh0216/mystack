<!-- doc-id: glue-iceberg-guide -->
<!-- lang: ko -->

[한국어](iceberg.ko.md) | [English](iceberg.md)

# Glue Iceberg 안내

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 안내는 지원하는 Apache Iceberg Java GlueCatalog lifecycle과 metadata 경계를 다룹니다.

<!-- section: reading-order -->
## 읽는 순서

1. [Open Table Format](glue-open-table-format.ko.md) — Iceberg metadata의 Glue 요청 경계
2. [Commit](glue-iceberg-commits.ko.md) — 원자적 metadata compare-and-swap과 retry
3. [Evolution](glue-iceberg-evolution.ko.md) — schema, partition, sort evolution
4. [Row-level DML](glue-iceberg-row-level-dml.ko.md) — COW/MOR write 경로
5. [Snapshot, ref, procedure](glue-iceberg-snapshots-refs-procedures.ko.md) — query와 maintenance
   의미론
6. [Lifecycle](glue-iceberg-lifecycle.ko.md) — rename, drop, purge, managed table
7. [Table optimizer](glue-table-optimizers.ko.md) — Glue optimizer control-plane operation

고정한 Apache Iceberg Java GlueCatalog 시나리오로 이 경로를 검증합니다. PyIceberg, Flink, Trino,
Glue Iceberg REST endpoint는 명시적인 제외 범위입니다.

<!-- section: sources -->
## 공식 참고 자료

- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
