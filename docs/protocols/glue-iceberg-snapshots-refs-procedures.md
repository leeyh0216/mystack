<!-- doc-id: protocols/glue-iceberg-snapshots-refs-procedures -->
<!-- lang: en -->

[한국어](glue-iceberg-snapshots-refs-procedures.ko.md) | [English](glue-iceberg-snapshots-refs-procedures.md)

# Iceberg snapshots, references, and procedures through GlueCatalog

<!-- toc:start -->
## Contents

- [Responsibility boundary](#responsibility-boundary)
- [Guaranteed profile](#guaranteed-profile)
- [Glue wire and atomicity contract](#glue-wire-and-atomicity-contract)
- [Verification evidence](#verification-evidence)
- [Logging and repair locations](#logging-and-repair-locations)
- [Limits](#limits)
- [Official sources](#official-sources)
<!-- toc:end -->

This contract fixes the snapshot inspection and maintenance surface for Glue 5.0, Spark 3.5.4,
and Iceberg 1.7.1. The SQL behavior comes from Iceberg's official
[queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/),
[DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/), and
[procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/) documentation.

<!-- section: responsibility -->
## Responsibility boundary

Apache Iceberg parses and executes time travel, reference DDL, metadata-table queries, snapshot
management, compaction, expiration, and orphan cleanup. It writes metadata and data objects through
its S3 FileIO. Mystack neither reimplements these algorithms nor interprets snapshot JSON during a
commit. Mystack losslessly stores each client-produced Glue `TableInput` and atomically advances its
`metadata_location` with the expected `VersionId`. LocalStack supplies the configured S3 endpoint.

<!-- section: behavior -->
## Guaranteed profile

The pinned real-runtime scenario guarantees:

| Area | Evidence |
| --- | --- |
| Time travel | `VERSION AS OF` and `TIMESTAMP AS OF` return the first snapshot's exact row |
| References | branch/tag creation at a snapshot, branch append, main isolation, and branch/tag reads |
| Metadata tables | non-empty `history`, `snapshots`, `files`, `manifests`, and `partitions` queries |
| Snapshot procedures | `rollback_to_snapshot`, `set_current_snapshot`, and an append `cherrypick_snapshot` return and publish the expected snapshot IDs |
| Maintenance | `rewrite_data_files` rewrites at least two small files and `rewrite_manifests` rewrites manifests without changing rows |
| Expiration | an unreferenced branch snapshot is explicitly expired while current rows remain readable |
| Orphan cleanup | a dedicated old candidate is returned by dry-run, remains in S3, is returned by the real removal, and is then absent from S3 |

Branches and tags are dropped before snapshot expiration. Orphan cleanup receives a one-row
`file_list_view`; it never lists or considers unrelated objects. The fixture table and object prefix
are unique to one E2E run.

<!-- section: wire -->
## Glue wire and atomicity contract

Every reference DDL or procedure that changes table metadata eventually sends `UpdateTable` with
the last observed Glue `VersionId`. A mismatch returns HTTP 400 `ConcurrentModificationException`
before durable or visible state changes. The focused contract proves exact versions, an unchanged
catalog after a stale rollback candidate, and the absence of its metadata pointer from archives.
This follows AWS Glue [`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
and [`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html).

<!-- section: evidence -->
## Verification evidence

`glue/tests/test_iceberg_snapshot_ref_catalog.py` is the fast AWS JSON 1.1 pointer contract.
`glue/tests/workloads/iceberg_snapshot_refs.py` is the CI-only real Iceberg scenario, invoked by
`tests/e2e/test_glue_spark_catalog.py` through the public Proxy. The host test reads the final Glue
pointer with boto3, downloads the metadata JSON, checks that only `main` remains, proves the expired
snapshot is absent, and confirms the orphan object returns S3 `404`/`NoSuchKey`. All waits and the
Spark process use the compatibility case's configured timeout.

<!-- section: observability -->
## Logging and repair locations

Every SQL/procedure/S3 side-effect boundary emits `MYSTACK_E2E_SCENARIO` before, after, or with only
the safe exception type. Existing `glue.iceberg.commit.*` and `glue.repository.*` events expose the
catalog CAS and persistence boundary without logging SQL, table locations, or payloads.

When an Iceberg or Spark upgrade breaks this profile, inspect:

1. `glue/tests/workloads/iceberg_snapshot_refs.py` for SQL, result-schema, or procedure changes.
2. `test_support/iceberg_metadata.py` for Iceberg metadata-format representation changes.
3. `glue/adapters/inbound/aws_table.py` for modeled Glue request-member changes.
4. `glue/application/table.py` and `glue/adapters/outbound/sqlite_catalog/repository.py` for CAS
   or archive loss.
5. Typed pytest compatibility annotations for pinned runtime and capability evidence.

<!-- section: limits -->
## Limits

Rename/drop/purge is covered by the [Iceberg lifecycle contract](glue-iceberg-lifecycle.md).
This contract does not guarantee scheduled optimizer services, every procedure option, or every
metadata table. Open Table Format inputs are covered by the separate
[input contract](glue-open-table-format.md). Authentication, authorization, IAM, Lake Formation,
cross-account/cross-Region, PyIceberg, Flink, and Trino are explicitly excluded.

<!-- section: sources -->
## Official sources

- [AWS Glue: Using the Iceberg framework](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 Spark queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg 1.7.1 Spark procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/)
- [Apache Iceberg 1.7.1 branching and tagging](https://iceberg.apache.org/docs/1.7.1/branching/)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
