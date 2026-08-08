<!-- doc-id: protocols/glue-iceberg-row-level-dml -->
<!-- lang: en -->

[한국어](glue-iceberg-row-level-dml.ko.md) | [English](glue-iceberg-row-level-dml.md)

# Iceberg row-level DML through GlueCatalog

This contract fixes the supported row-level write behavior for the Glue 5.0, Spark 3.5.4, and
Iceberg 1.7.1 profile. It follows Iceberg's official
[Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/) and
[write-mode configuration](https://iceberg.apache.org/docs/1.7.1/configuration/) contracts.

<!-- section: responsibility -->
## Responsibility boundary

Iceberg's Spark extensions plan and execute `INSERT`, `UPDATE`, `DELETE`, and `MERGE`; write data
and delete files; and create manifests, snapshot summaries, and table metadata in S3. Mystack does
not parse SQL, evaluate rows, or implement copy-on-write or merge-on-read. It losslessly stores the
client-produced Glue `TableInput` and atomically commits the new `metadata_location` when the
expected `VersionId` is current.

The pointer transaction is the existing [Iceberg GlueCatalog commit contract](glue-iceberg-commits.md).
The S3 objects and snapshot semantics follow the Iceberg
[snapshot specification](https://iceberg.apache.org/spec/#snapshots).

<!-- section: behavior -->
## Guaranteed profile

The pinned real-runtime scenario guarantees:

| Area | Evidence |
| --- | --- |
| Append | `INSERT INTO` retains existing rows and adds a new row |
| Overwrite | Dynamic `INSERT OVERWRITE` replaces only the represented identity partition and preserves the other partition |
| Copy-on-write | `UPDATE`, `DELETE FROM`, and all matched/not-matched `MERGE INTO` actions produce the expected rows with zero current delete files |
| Merge-on-read | The same row-level mutation families produce the expected rows and leave real Iceberg v2 delete-file evidence |
| Merge validation | Two source rows matching one target row fail, as required by Iceberg's Spark write contract |
| Failed commit | The failed merge creates neither a Glue version nor an Iceberg snapshot; the previous committed rows and pointer remain current |
| Contention | The deterministic stale-pointer contract rejects a losing candidate, while the existing two-container test proves Iceberg refresh/retry over the same Glue CAS path |

`write.delete.mode`, `write.update.mode`, and `write.merge.mode` are set explicitly to
`copy-on-write` or `merge-on-read`; implicit client defaults are not used as evidence. The table is
format version 2 because merge-on-read delete files are a v2 feature.

<!-- section: wire -->
## Glue wire and failure contract

Every successful row-level Iceberg commit sends one modeled Glue `UpdateTable` with the previous
`VersionId` and next metadata pointer. COW has six successful snapshots/Glue pointer changes in the
scenario; MOR has four. Exact final Glue versions and Iceberg snapshot counts prove that the
expected invalid merge did not publish an extra candidate.

A stale `UpdateTable` returns HTTP 400 `ConcurrentModificationException` before persistence. The
current pointer, archive, and all stored table properties remain unchanged. These members and the
response code follow AWS Glue [`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
and [`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html).
When the Glue commit succeeds, all subsequent row and file semantics remain Iceberg-owned.

<!-- section: evidence -->
## Verification evidence

The fast `glue/tests/test_iceberg_row_level_catalog.py` contract runs through the AWS JSON 1.1
boundary. It commits one MOR pointer, submits a stale delete candidate, and proves the modeled
error, unchanged durable state, exact current pointer, and absence of the losing metadata location
from every table version.

The CI-only `tests/e2e/test_glue_spark_catalog.py` scenario runs in the official Glue 5 image through
the public Proxy and LocalStack. It asserts rows after each important boundary, reads the final
pointer with boto3, downloads the real table metadata JSON from S3, and verifies format version,
write-mode properties, snapshot count, current snapshot, and total delete-file evidence. Every
process and test wait remains bounded by the compatibility case's explicit timeout.

<!-- section: observability -->
## Logging and repair locations

Each DML boundary emits only its scenario name, phase, and safe exception class as
`MYSTACK_E2E_SCENARIO`. Existing `glue.iceberg.commit.*` and `glue.repository.*` events expose the
pointer decision and persistence lifecycle using fingerprints rather than SQL bodies or S3 paths.

If an upgraded client breaks this profile, inspect:

1. `glue/scripts/e2e/iceberg_row_level.py` for Spark SQL or Iceberg write-mode changes.
2. `test_support/iceberg_metadata.py` for Iceberg snapshot-summary representation changes.
3. `glue/adapters/inbound/aws_table.py` for Glue request-member changes.
4. `glue/application/table.py` and `glue/adapters/outbound/repository.py` for CAS/version loss.
5. `compatibility/cases.yaml` for pinned profile and scenario drift.

<!-- section: limits -->
## Limits

Snapshot time travel, branch/tag writes, metadata tables, and procedures are covered by the
[snapshot/reference/procedure contract](glue-iceberg-snapshots-refs-procedures.md). This row-level
contract does not guarantee rename/drop/purge. It also excludes authentication, authorization, IAM,
Lake Formation, cross-account/cross-Region, Open Table Format APIs, PyIceberg, Flink, and Trino.

<!-- section: sources -->
## Official sources

- [AWS Glue: Using the Iceberg framework](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/)
- [Apache Iceberg 1.7.1 configuration](https://iceberg.apache.org/docs/1.7.1/configuration/)
- [Apache Iceberg snapshot specification](https://iceberg.apache.org/spec/#snapshots)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
