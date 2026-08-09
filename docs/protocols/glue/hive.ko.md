<!-- doc-id: glue-hive-guide -->
<!-- lang: ko -->

[한국어](hive.ko.md) | [English](hive.md)

# Glue Hive 안내

<!-- toc:start -->
## 목차

- [읽는 순서](#읽는-순서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 안내는 Glue Data Catalog를 Hive metastore로 사용하는 Spark SQL 경로를 다룹니다.

<!-- section: reading-order -->
## 읽는 순서

1. [Partition expression](glue-partition-expressions.ko.md) — Spark SQL에서 전달하는 type 기반 pruning
2. [Hive partition DDL](glue-hive-partition-ddl.ko.md) — add/drop/rename/repair 동작
3. [Hive table ALTER](glue-hive-table-alter.ko.md) — 지원하는 메타데이터 mutation 변형
4. [Batch partition 오류](glue-partition-batch-errors.ko.md) — Hive 메타데이터 API 작업 뒤의 Glue
   control-plane 결과

이 범위를 바꾸면 Spark 클라이언트 lab 또는 `tests/e2e/test_glue_spark_catalog.py`를 실행합니다. Runtime
경로는 Glue Data Catalog를 Spark Hive metastore로 사용하며 범용 Hive Metastore 서비스는 아닙니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue Data Catalog as Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
