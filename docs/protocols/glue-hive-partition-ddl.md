<!-- doc-id: protocols/glue-hive-partition-ddl -->
<!-- lang: en -->

[한국어](glue-hive-partition-ddl.ko.md) | [English](glue-hive-partition-ddl.md)

# Spark Hive partition DDL through Glue

Mystack does not parse Spark SQL. Spark 3.5 owns DDL syntax, type checking, `IF EXISTS`/
`IF NOT EXISTS`, S3 directory discovery, cache invalidation, and command errors. Mystack provides
the Glue catalog operations used by the official Glue Hive metastore client. This boundary follows
AWS's description of the [Data Catalog as an external Hive
metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html).

<!-- section: mapping -->
## DDL-to-Glue mapping

| Spark/Hive behavior | Glue catalog surface |
| --- | --- |
| `ADD PARTITION`, multi-add | `CreatePartition`, `BatchCreatePartition` |
| Existence checks and `SHOW PARTITIONS` | `GetPartition`, `BatchGetPartition`, `GetPartitions` |
| Partition rename and `SET LOCATION` | `UpdatePartition`, `BatchUpdatePartition` |
| `DROP PARTITION` | `DeletePartition`, `BatchDeletePartition` |
| `MSCK REPAIR` / `RECOVER PARTITIONS` ADD | Spark scans S3, then creates discovered Glue partitions |
| `MSCK REPAIR ... DROP` | Spark compares S3 with Glue, then deletes missing Glue partitions |
| `MSCK REPAIR ... SYNC` | The ADD and DROP paths above in one Spark command |

The DDL forms and typed partition literals are defined by the official [Spark 3.5.4 `ALTER
TABLE` reference](https://spark.apache.org/docs/3.5.4/sql-ref-syntax-ddl-alter-table.html). Repair
mode behavior follows the official [Spark `REPAIR TABLE`
reference](https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-repair-table.html).

<!-- section: semantics -->
## Catalog and side-effect semantics

Partition identity is the ordered tuple from the table's `PartitionKeys`; values are preserved as
strings, including `/`, `=`, spaces, and Unicode. Rename changes that tuple and rejects a destination
that already exists. `SET LOCATION` replaces the partition input supplied by the Hive client while
preserving creation time. Partition mutations do not create a new table version.

Glue batch APIs are deterministic partial-success operations: entries execute in request order,
successful entries remain committed, and each failed entry appears in `Errors`. The single-item
operations fail the whole request. Spark may perform its own preflight checks before selecting one
of these APIs; therefore the SQL-level exception is Spark-owned even though the resulting metadata
is Glue-owned.

Glue metadata calls never create, copy, rename, or delete S3 objects in the emulator. Spark/Hadoop
owns repair discovery and any filesystem effects. The CI contract uses an external table and proves
that dropping its catalog partition leaves existing S3 data intact. `SET LOCATION` updates metadata
without copying data.

<!-- section: diagnose -->
## Verification and diagnosis

A focused real-port boto3 contract runs add, partial multi-add, rename, location update, collision,
partial delete, complex values, and table-version invariance. The CI-only Glue 5/Spark 3.5 scenario
runs single/multi add, both `IF` variants, rename, location update, drop, default/ADD/DROP/SYNC
repair, and `ALTER TABLE RECOVER PARTITIONS` against LocalStack S3. It emits
`MYSTACK_E2E_SCENARIO` before and after every SQL boundary and uses the configured E2E timeout.

For a future Spark or Glue Hive client change, inspect the generic AWS dispatcher operation and
payload-fingerprint logs plus repository transaction events. If the SQL never reaches Mystack,
update the Spark/Glue client configuration or E2E SQL. If the operation shape changes, update the
inbound partition/batch operation family. If metadata rules change, update the partition command or
batch application handler; repository adapters remain collection persistence only.

<!-- section: exclusions -->
## Exclusions

Hive authorization, locks, transactions, statistics, crawler discovery, managed-table data
deletion, and undocumented client behavior are not guaranteed here. General authentication,
authorization, Lake Formation, cross-account, and cross-Region semantics remain outside project
scope.

<!-- section: sources -->
## Official sources

- [AWS Glue Data Catalog support for Spark SQL jobs](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [AWS Glue Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Spark 3.5.4 ALTER TABLE](https://spark.apache.org/docs/3.5.4/sql-ref-syntax-ddl-alter-table.html)
- [Spark REPAIR TABLE](https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-repair-table.html)
