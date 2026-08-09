<!-- doc-id: glue-catalog-architecture -->
<!-- lang: ko -->

[한국어](glue-catalog-architecture.ko.md) | [English](glue-catalog-architecture.md)

# Glue Catalog 아키텍처

<!-- toc:start -->
## 목차

- [Catalog 요청 경로](#catalog-요청-경로)
- [Persistence와 Iceberg 경계](#persistence와-iceberg-경계)
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

<!-- section: constraints -->
## Local 제약

Glue Job, JobRun, Crawler, IAM, Lake Formation은 범위 밖입니다. Management Console은 인증 없는 local read
model이며 mutation은 계속 public AWS endpoint를 사용합니다. 신뢰하지 않는 network에는 노출하지 마세요.

<!-- section: references -->
## 참고 자료

- [Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Glue Data Catalog Hive 통합](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Iceberg with Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [SQLite runtime 경계](protocols/glue-sqlite-runtime.ko.md)
