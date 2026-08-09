<!-- doc-id: glue-catalog-architecture -->
<!-- lang: ko -->

[한국어](glue-catalog-architecture.ko.md) | [English](glue-catalog-architecture.md)

# Glue Catalog 아키텍처

<!-- toc:start -->
## 목차

- [Catalog 요청 경로](#catalog-요청-경로)
- [Persistence와 Iceberg 경계](#persistence와-iceberg-경계)
- [상한이 있는 Catalog list query 경로](#상한이-있는-catalog-list-query-경로)
- [Local 제약](#local-제약)
- [참고 자료](#참고-자료)
<!-- toc:end -->

<!-- section: request -->
## Catalog 요청 경로

Glue 요청은 public Proxy, AWS JSON 1.1 요청 구조 검증, operation-family adapter, database/table/partition/
optimizer application handler를 차례로 통과합니다. Domain error는 inbound 경계에서만 modeled Glue error로
변환합니다.

```text
Glue client -> proxy -> Glue AWS JSON adapter -> application command/query
                                                |                 |
                                                v                 v
                                         domain invariant    catalog repository
```

<!-- section: persistence -->
## Persistence와 Iceberg 경계

Production catalog는 SQLite 전용입니다. Application command/query port는 DB-API와 SQL을 outbound adapter에
가두고, normalized row에는 catalog entity, typed partition projection, 안정적인 segment assignment를 저장합니다.
`GetPartitions`는 지원되는 bound AST expression을 parameterized SQLite predicate로 compile하고
`(order_key, partition_id)` keyset continuation을 사용하므로 한 page를 위해 catalog 전체를 materialize하지 않습니다.
Hive와 Iceberg client는 public Glue endpoint를 사용하며 table metadata와 data file은 client/S3가 소유합니다.

```text
Spark Hive / Iceberg -> Glue Catalog API -> table VersionId CAS
                                           |             |
                                           v             v
                                   catalog metadata   LocalStack S3 metadata/data
```

Open Table Format orchestration은 request를 검증하고 storage port로 metadata candidate를 만들며 CAS로 catalog
pointer를 commit하고 실패하면 보상합니다. 일반 client 소유 Iceberg metadata location은 parse하거나 rewrite하지
않습니다.

<!-- section: bounded-query -->
## 상한이 있는 Catalog list query 경로

Database와 table list는 SQLite `ORDER BY`와 `LIMIT page_size + 1`을 사용합니다. Continuation에는
context fingerprint와 surrogate row ID만 저장하고 adapter가 같은 scope 안에서 private sort key를 다시
해결합니다. `GetPartitions`는 ANTLR/evaluator 소유권을 application에 유지하며, outbound adapter는 이미
bind된 AST를 parameter와 ordinal 기반 SQL alias로 compile합니다.

```text
AWS GetPartitions
  -> token / segment / grammar validation
  -> resolved table + bound partition-key types
  -> evaluator error-order probe 1건
  -> SQLite projections + persisted segment join + predicate
  -> (order_key, partition_id) seek + LIMIT n + 1
  -> Glue PartitionList + opaque NextToken
```

이 AWS request path에는 total-count query나 Catalog 전체 materialization이 없습니다. Management read
model은 별도 query port로 필요한 count를 명시적으로 요청합니다. Operator와 오류 순서 계약은
[partition-expression protocol](protocols/glue/glue-partition-expressions.ko.md)을 참고하세요.

<!-- section: constraints -->
## Local 제약

Glue Job, JobRun, Crawler, IAM, Lake Formation은 범위 밖입니다. Management Console은 인증 없는 local read
model이며 mutation은 계속 public AWS endpoint를 사용합니다. 신뢰하지 않는 network에는 노출하지 마세요.

<!-- section: references -->
## 참고 자료

- [Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [Glue Data Catalog Hive 통합](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Iceberg with Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [SQLite runtime 경계](protocols/glue/glue-sqlite-runtime.ko.md)
- [SQLite query planner](https://www.sqlite.org/queryplanner.html)
