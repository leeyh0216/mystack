<!-- doc-id: protocols/glue-iceberg-evolution -->
<!-- lang: en -->

[한국어](glue-iceberg-evolution.ko.md) | [English](glue-iceberg-evolution.md)

# Iceberg metadata evolution through GlueCatalog

<!-- toc:start -->
## Contents

- [Responsibility boundary](#responsibility-boundary)
- [Guaranteed evolution profile](#guaranteed-evolution-profile)
- [Glue wire contract](#glue-wire-contract)
- [Verification evidence](#verification-evidence)
- [Logging and repair locations](#logging-and-repair-locations)
- [Limits](#limits)
- [Official sources](#official-sources)
<!-- toc:end -->

This contract fixes the supported Apache Iceberg 1.7.1 partition, schema, sort, and identifier
evolution behavior for the Glue 5.0 interoperability profile. The syntax and semantic rules come
from Iceberg's [partitioning](https://iceberg.apache.org/docs/1.7.1/partitioning/),
[evolution](https://iceberg.apache.org/docs/1.7.1/evolution/), and
[Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/) documentation.

<!-- section: responsibility -->
## Responsibility boundary

Spark and the Iceberg 1.7.1 runtime create data files, manifests, snapshots, table metadata JSON,
partition specs, schemas, sort orders, and identifier-field IDs in S3. Mystack does not implement
or interpret those structures. It preserves the `TableInput` sent by Iceberg and atomically swaps
the Glue `Parameters.metadata_location` pointer with the expected `VersionId`, as defined by the
[Iceberg GlueCatalog commit contract](glue-iceberg-commits.md).

Iceberg partition fields therefore do not become Glue Hive `PartitionKeys` or Glue partition rows.
This is the hidden-partitioning model: queries filter source columns while Iceberg derives and
prunes partition values without exposing the physical partition layout to callers.

<!-- section: behavior -->
## Guaranteed evolution profile

The fixed Glue 5.0/Spark 3.5.4/Iceberg 1.7.1 profile exercises the following behavior in one
table-driven real-runtime scenario:

| Area | Guaranteed forms |
| --- | --- |
| Partition transforms | identity, `bucket`, `truncate`, `year`, `month`, `day`, and `hour` |
| Partition evolution | add, drop, and replace fields while retaining historical specs |
| Schema evolution | add/drop/rename top-level and nested fields |
| Safe widening | `int` to `long`, `float` to `double`, and decimal precision increase at the same scale |
| Sort order | ordered, unordered, and replacement order with direction and null ordering |
| Identifier fields | set, drop, and set again on a required field |
| Read behavior | rows written before and after evolution remain readable; source-column filters return the expected result |

These are metadata-only Iceberg operations. Existing files are not rewritten when a partition spec
or schema changes. That behavior follows Iceberg's documented schema and partition evolution
model; it is not extra logic inside the Glue emulator.

<!-- section: wire -->
## Glue wire contract

For each Iceberg commit, the AWS JSON 1.1 boundary receives an `UpdateTable` carrying the next
`metadata_location`, the current Glue `VersionId`, and the client-produced table definition. A
matching version publishes one new table version and archives the previous definition unless
`SkipArchive=true`. A stale version returns `ConcurrentModificationException` and leaves both the
current table and archived versions unchanged. `GetTable` and `GetTableVersions` return every
stored pointer and client-supplied column/type string without creating synthetic partition keys.

The authoritative request and response members are the AWS Glue
[`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html),
[`GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html), and
[`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
contracts. Iceberg's [table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
defines the S3 JSON reached through the pointer.

<!-- section: evidence -->
## Verification evidence

The fast `glue/tests/test_iceberg_evolution_catalog.py` contract drives the real AWS JSON boundary.
It proves lossless pointer/column/property versioning, absence of synthetic Hive partition keys,
archive order, stale-writer error code, and no state change after a conflict.

The CI-only `tests/e2e/test_glue_spark_catalog.py` scenario runs the official Glue 5 image against
the public Proxy and LocalStack. It performs every form in the table above, reads rows from both
schemas, fetches the final `metadata_location` through boto3, downloads the actual metadata JSON
through S3 `GetObject`, and resolves field IDs rather than relying on JSON list positions. The test
asserts historical/current partition transforms, current schema and nested fields, safe widened
types, identifier fields, and the full sort order.

<!-- section: observability -->
## Logging and repair locations

`MYSTACK_E2E_SCENARIO` emits a safe before/after record for each named DDL boundary, while
`glue.iceberg.commit.*` and `glue.repository.*` expose version decisions and persistence without
logging table bodies or S3 paths. If a Spark or Iceberg upgrade breaks this profile, inspect:

1. `glue/scripts/e2e/iceberg_evolution.py` for changed Spark DDL or runtime behavior.
2. `test_support/iceberg_metadata.py` for a changed Iceberg metadata-spec representation.
3. `glue/adapters/inbound/aws_table.py` for changed Glue wire members.
4. `glue/application/table.py` and `glue/adapters/outbound/repository.py` for pointer/version loss.
5. Typed pytest compatibility annotations for the resolved runtime, scenario, and evidence declaration.

<!-- section: limits -->
## Limits

Row-level writes are covered separately by the [Iceberg row-level DML
contract](glue-iceberg-row-level-dml.md). Snapshot, reference, metadata-table, and procedure behavior
is covered by the [snapshot/reference/procedure contract](glue-iceberg-snapshots-refs-procedures.md).
Rename/drop/purge is covered by the [Iceberg lifecycle contract](glue-iceberg-lifecycle.md).
This evolution contract does not redefine it. Open Table Format inputs are covered by the separate
[input contract](glue-open-table-format.md). Authentication, authorization, IAM, Lake Formation,
cross-account/cross-Region behavior, PyIceberg, Flink, and Trino remain explicit project exclusions.

<!-- section: sources -->
## Official sources

- [AWS Glue: Using the Iceberg framework](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 partitioning](https://iceberg.apache.org/docs/1.7.1/partitioning/)
- [Apache Iceberg 1.7.1 evolution](https://iceberg.apache.org/docs/1.7.1/evolution/)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [Amazon S3 `GetObject`](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)
