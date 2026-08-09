<!-- doc-id: glue-catalog-architecture -->
<!-- lang: en -->

[한국어](glue-catalog-architecture.ko.md) | [English](glue-catalog-architecture.md)

# Glue Catalog architecture

<!-- toc:start -->
## Contents

- [Catalog request path](#catalog-request-path)
- [Persistence and Iceberg boundary](#persistence-and-iceberg-boundary)
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

The current production catalog is JSON-backed with atomic candidate publication and a bounded
cross-process lock. The source-built SQLite runtime is a verified capability gate only; normalized
SQLite persistence is not yet active. Hive and Iceberg clients use the public Glue endpoint while
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

<!-- section: constraints -->
## Local constraints

Glue Job, JobRun, Crawler, IAM, and Lake Formation are outside scope. The management Console is a
local unauthenticated read model; mutations still use the public AWS endpoint. Do not expose it on
an untrusted network.

<!-- section: references -->
## References

- [Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Glue Data Catalog Hive integration](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Iceberg with Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [SQLite runtime boundary](protocols/glue-sqlite-runtime.md)
