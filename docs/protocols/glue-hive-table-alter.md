<!-- doc-id: protocols/glue-hive-table-alter -->
<!-- lang: en -->

[한국어](glue-hive-table-alter.ko.md) | [English](glue-hive-table-alter.md)

# Spark Hive table ALTER through Glue

Mystack preserves the Glue catalog request selected by Spark and the official Glue Hive metastore
client; it does not parse Spark SQL. Spark owns SQL analysis, V1/V2 capability checks, cache
invalidation, and SQL exceptions. Mystack owns `UpdateTable`, immutable table versions, and atomic
catalog persistence. This boundary follows AWS's documented [Data Catalog external Hive metastore
integration](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html).

<!-- section: mapping -->
## SQL and protocol mapping

| Spark Hive operation | Observed protocol boundary | Mystack guarantee |
| --- | --- | --- |
| `ADD COLUMNS`, including complex Glue type strings | `GetTable`, then `UpdateTable` with a complete `TableInput` | Lossless replacement and a new table version |
| `ALTER/CHANGE COLUMN ... COMMENT` | `UpdateTable` | Existing name/type/order are preserved; comment changes |
| `SET/UNSET TBLPROPERTIES` | `UpdateTable` | Complete parameter map supplied by Spark is preserved |
| `SET SERDE` / `SET SERDEPROPERTIES` | `UpdateTable` | SerDe class and property map are preserved |
| Table `SET LOCATION` / `SET FILEFORMAT` | `UpdateTable` | StorageDescriptor replacement is preserved; no S3 objects are moved |
| Partition location/Serde changes | Partition APIs | Covered by the [partition DDL contract](glue-hive-partition-ddl.md) |
| V1 `DROP COLUMN`, `RENAME COLUMN`, `REPLACE COLUMNS`, or type change | Spark rejects the command before Glue | Failure must not mutate catalog state |
| Hive table `RENAME TO` | Official Glue Hive client rejects before `UpdateTable` | `Table rename is not supported`; source metadata remains |

Spark documents `DROP COLUMN`, `RENAME COLUMN`, and `REPLACE COLUMNS` as V2-only. Spark 3.5's V1
`AlterTableChangeColumnCommand` accepts comment/default changes but rejects a changed column name or
type. The official Glue Hive client's `alterTable` independently rejects a changed table name.
These are client-owned outcomes, so Mystack must not add a private SQL parser or pretend that an AWS
request occurred.

<!-- section: semantics -->
## Glue API and persistence semantics

`UpdateTable` replaces the stored definition with the complete `TableInput`; it does not merge
missing fields. Names are folded to lowercase for Hive compatibility, while column and type strings
remain lossless. By default, the previous definition becomes an archived `TableVersion` and the
current numeric `VersionId` advances. `SkipArchive=true` advances the current version without
retaining the replaced definition. A supplied `VersionId` is a compare-and-swap precondition.

The current Glue model also exposes top-level `UpdateTable.Name`. This is a direct Glue API surface,
not the rename path used by the official Hive client. When `Name` identifies the source and
`TableInput.Name` differs, Mystack atomically moves the table and all catalog partitions. A missing
source fails, an existing target is not overwritten, and a case-only change normalizes to the same
Hive name. `UpdateTable` has one `DatabaseName`, so it cannot move a table across databases.
Persistence failure publishes neither the candidate table nor moved partitions.

Catalog metadata changes never copy, rename, or delete S3 data. Spark/Hadoop owns filesystem side
effects. Authorization, locks, statistics fidelity, and cache behavior are outside the emulator's
catalog boundary.

<!-- section: diagnose -->
## Verification and diagnosis

The focused real-port boto3 contract covers full StorageDescriptor/complex-column preservation,
properties, SerDe, location, default archive, `SkipArchive`, optimistic version checks, direct API
rename, target collision, case folding, missing source, and partition preservation. A persistence
contract injects a durable-save failure and proves that table and partition names roll back
together.

The CI-only Glue 5/Spark 3.5 scenario reuses one Spark session. It exercises successful column,
property, SerDe, and location mutations, then proves that V1 drop/rename/type changes and Hive table
rename fail without changing the final Glue definition. Each SQL boundary emits a structured
`MYSTACK_E2E_SCENARIO` event and inherits the configured E2E timeout.

If a future Spark or Glue client update breaks this path, first inspect whether a generic AWS
dispatcher log contains `UpdateTable`. No request means the Spark/client adapter or SQL expectation
changed. A changed payload means the inbound table operation family or botocore contract changed.
Correct payload with wrong state points to `TableCommands`; serialization/restart problems point to
the repository adapter. This keeps protocol translation, application policy, and persistence
responsibilities separate.

<!-- section: exclusions -->
## Exclusions

Mystack does not add V2 column operations to Spark's V1 Hive catalog, emulate Hive locks or
authorization, move managed-table data, or compare behavior with a live AWS account. Authentication,
authorization, IAM, Lake Formation, cross-account, and cross-Region semantics remain outside scope.

<!-- section: sources -->
## Official sources

- [AWS Glue UpdateTable](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue GetTableVersions](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
- [AWS Glue Data Catalog as a Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark 3.5 ALTER TABLE](https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html)
- [Spark 3.5.4 V1 ALTER implementation](https://github.com/apache/spark/blob/v3.5.4/sql/core/src/main/scala/org/apache/spark/sql/execution/command/ddl.scala)
- [Official Glue Hive client `alterTable`](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/branch-3.4.0/aws-glue-datacatalog-client-common/src/main/java/com/amazonaws/glue/catalog/metastore/GlueMetastoreClientDelegate.java)
