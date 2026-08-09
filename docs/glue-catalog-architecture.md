<!-- doc-id: glue-catalog-architecture -->
<!-- lang: en -->

[한국어](glue-catalog-architecture.ko.md) | [English](glue-catalog-architecture.md)

# Glue Catalog architecture

<!-- toc:start -->
## Contents

- [Catalog request path](#catalog-request-path)
- [Persistence and Iceberg boundary](#persistence-and-iceberg-boundary)
- [Bounded Catalog list query path](#bounded-catalog-list-query-path)
- [Local constraints](#local-constraints)
- [References](#references)
<!-- toc:end -->

<!-- section: request -->
## Catalog request path

Glue requests traverse the public Proxy, AWS JSON 1.1 shape validation, an operation-family adapter,
and focused database/table/partition/optimizer application handlers. Domain errors are translated
to modeled Glue errors only at the inbound boundary.

```text
Glue client -> proxy -> Glue AWS JSON adapter -> application command/query
                                                |                 |
                                                v                 v
                                         domain invariants   catalog repository
```

<!-- section: persistence -->
## Persistence and Iceberg boundary

The production catalog is SQLite-only. Application command/query ports keep DB-API and SQL inside
the outbound adapter; normalized rows retain catalog entities, typed partition projections, and
stable segment assignments. `GetPartitions` compiles supported bound AST expressions to
parameterized SQLite predicates and uses `(order_key, partition_id)` keyset continuations, so a
page does not materialize the catalog. Hive and Iceberg clients use the public Glue endpoint while
their table metadata and data files remain client/S3 owned.

```text
Spark Hive / Iceberg -> Glue Catalog API -> table VersionId CAS
                                           |             |
                                           v             v
                                   catalog metadata   LocalStack S3 metadata/data
```

Open Table Format orchestration validates the request, materializes a metadata candidate through a
storage port, commits the catalog pointer with CAS, and compensates on failure. The emulator does
not parse or rewrite ordinary client-owned Iceberg metadata locations.

<!-- section: bounded-query -->
## Bounded Catalog list query path

Database and table lists use SQLite `ORDER BY` plus `LIMIT page_size + 1`; a continuation stores a
context fingerprint and a surrogate row ID, then the adapter resolves the private sort key under the
same scope. `GetPartitions` retains ANTLR/evaluator ownership in the application, while the
outbound adapter compiles the already-bound AST into parameters and ordinal-derived SQL aliases.

```text
AWS GetPartitions
  -> token / segment / grammar validation
  -> resolved table + bound partition-key types
  -> one evaluator error-order probe
  -> SQLite projections + persisted segment join + predicate
  -> (order_key, partition_id) seek + LIMIT n + 1
  -> Glue PartitionList + opaque NextToken
```

There is no total-count query or full Catalog materialization in this AWS request path. Management
read models request explicit counts through a separate query port. See the
[partition-expression protocol](protocols/glue-partition-expressions.md) for the operator and
error-order contract.

<!-- section: constraints -->
## Local constraints

Glue Job, JobRun, Crawler, IAM, and Lake Formation are outside scope. The management Console is a
local unauthenticated read model; mutations still use the public AWS endpoint. Do not expose it on
an untrusted network.

<!-- section: references -->
## References

- [Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [Glue Data Catalog Hive integration](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Iceberg with Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [SQLite runtime boundary](protocols/glue-sqlite-runtime.md)
- [SQLite query planner](https://www.sqlite.org/queryplanner.html)
