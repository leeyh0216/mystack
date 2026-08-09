<!-- doc-id: protocols/glue/glue-iceberg-lifecycle -->
<!-- lang: en -->

[한국어](glue-iceberg-lifecycle.ko.md) | [English](glue-iceberg-lifecycle.md)

# Iceberg rename, drop, and purge through GlueCatalog

<!-- toc:start -->
## Contents

- [Responsibility boundary](#responsibility-boundary)
- [Rename sequence and guarantees](#rename-sequence-and-guarantees)
- [Drop and purge sequence](#drop-and-purge-sequence)
- [Failure and recovery boundary](#failure-and-recovery-boundary)
- [Verification evidence](#verification-evidence)
- [Logging and repair locations](#logging-and-repair-locations)
- [Limits](#limits)
- [Official sources](#official-sources)
<!-- toc:end -->

This contract fixes the table-lifecycle behavior for Glue 5.0, Spark 3.5.4, and Iceberg 1.7.1.
It follows Iceberg's official [Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
and the pinned
[`GlueCatalog` implementation](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416).

<!-- section: responsibility -->
## Responsibility boundary

Apache Iceberg parses the SQL and owns rename and purge as multi-system operations. Mystack does
not implement Iceberg's lifecycle algorithm. It supplies the individual modeled Glue
[`GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html),
[`CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html), and
[`DeleteTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html) operations.
Each operation commits its catalog state atomically. Iceberg's S3 FileIO owns tracked-file deletion,
and LocalStack supplies the configured object-store endpoint.

<!-- section: rename -->
## Rename sequence and guarantees

Pinned Iceberg 1.7.1 verifies the target namespace, loads the source, creates a destination Glue
table with the same metadata pointer and location, and then deletes the source without purge. If
source deletion fails, Iceberg attempts to delete the newly created destination as compensation.
This is a documented sequence, not one atomic Glue request.

The real-runtime scenario guarantees:

| Case | Guaranteed result |
| --- | --- |
| Rename in one namespace | Destination is readable and retains the row and S3 objects |
| Rename across namespaces | Destination gets Glue version `0`; location and `metadata_location` keep pointing to the original Iceberg table |
| Same normalized name or case-only target | Spark/Iceberg rejects the operation; no second logical table is created |
| Missing source or target namespace | The operation fails and no destination is published |
| Existing destination | `AlreadyExistsException` is preserved at the Glue boundary and both existing tables remain |
| Source-delete persistence failure | HTTP 500 `InternalServiceException`; the failed delete publishes no state, then Iceberg-style compensation removes only the destination |

Mystack normalizes catalog identifiers to lower case. The fast contract proves that `events` and
`EVENTS` collide before persistence and that missing reads return HTTP 400
`EntityNotFoundException`. Error evaluation uses Mystack's deterministic validation and operation
order; it does not compare requests against a live AWS account.

<!-- section: drop -->
## Drop and purge sequence

Iceberg 1.7.1 distinguishes these forms exactly as its Spark DDL documents:

- `DROP TABLE`: calls Glue `DeleteTable`; table data and metadata objects remain.
- `DROP TABLE ... PURGE`: loads the current Iceberg metadata, calls Glue `DeleteTable` first, then
  asks `CatalogUtil.dropTableData` to delete files tracked by that metadata.

The E2E scenario writes tracked data/metadata plus an untracked sentinel inside each table prefix.
Plain drop preserves every object. Purge removes the tracked Iceberg objects but preserves the
untracked sentinel and another unrelated object. This proves that Mystack does not implement an
unsafe recursive prefix delete. `IF EXISTS` retries are accepted by Spark/Iceberg and do not
recreate catalog state.

<!-- section: failure -->
## Failure and recovery boundary

Rename compensation is best effort across multiple Glue calls, while each Mystack call remains an
atomic catalog transaction. A failed source `DeleteTable` leaves both source and destination
visible until Iceberg's compensation removes the destination; the source is never partially
deleted.

Purge is deliberately not transactional across Glue and S3. The pinned implementation deletes the
Glue entry before tracked S3 files. If S3 deletion later fails, retrying SQL with `IF EXISTS` cannot
reload the missing catalog pointer. Recovery therefore requires the previously captured metadata
location or a separately controlled orphan-file cleanup. Mystack does not claim stronger
atomicity than Iceberg provides.

<!-- section: evidence -->
## Verification evidence

`glue/tests/test_iceberg_lifecycle_catalog.py` fixes the modeled errors, pointer copy, atomic delete,
and compensation sequence without Spark. `glue/tests/workloads/iceberg_lifecycle.py` runs the real
Iceberg SQL in the Glue image. `tests/e2e/test_glue_spark_catalog.py` verifies the resulting Glue
definitions with boto3 and object presence through the public Proxy and S3 endpoint. The Spark
process and test use the configured E2E timeout.

<!-- section: observability -->
## Logging and repair locations

Every scenario SQL and S3 side effect emits `MYSTACK_E2E_SCENARIO` before, after, or with a safe
exception type. `glue.repository.transaction.*` and `glue.repository.persistence.*` events identify
operation, resource fingerprint, side-effect phase, rollback, and a repair hint without exposing
table documents or object contents.

When an upgrade breaks this profile, inspect:

1. `glue/tests/workloads/iceberg_lifecycle.py` for Spark SQL or result changes.
2. Iceberg `GlueCatalog.renameTable` and `dropTable` for changed call ordering.
3. `glue/adapters/inbound/aws_table.py` for modeled request-member drift.
4. `glue/application/table.py` and `glue/adapters/outbound/sqlite_catalog/repository.py` for
   atomicity regressions.
5. Typed pytest compatibility annotations for the pinned runtime and capability evidence.

<!-- section: limits -->
## Limits

This profile does not make rename or purge atomic across Glue and S3, emulate scheduled optimizer
services, or guarantee recovery from an S3 deletion failure after catalog deletion. Authentication,
authorization, IAM, Lake Formation, cross-account/cross-Region, PyIceberg, Flink, and Trino are
excluded. Open Table Format inputs are covered separately by the [input contract](glue-open-table-format.md).

<!-- section: sources -->
## Official sources

- [AWS Glue `GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html)
- [AWS Glue `CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html)
- [AWS Glue `DeleteTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg 1.7.1 `GlueCatalog`](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416)
