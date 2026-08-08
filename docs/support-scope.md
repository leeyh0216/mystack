<!-- doc-id: support-scope -->
<!-- lang: en -->

[한국어](support-scope.ko.md) | [English](support-scope.md)

# Support scope

<!-- section: overview -->
## Overview

This document distinguishes implemented behavior from long-term targets. “Target” never means that the current build is already compatible.

| Area | Current status | Target |
| --- | --- | --- |
| Extensible proxy registry | Implemented, unit tested | Any AWS JSON/SigV4 emulator can register without proxy code changes |
| AWS JSON 1.1 codec/model validation | Implemented, unit tested | EMR and Glue modeled request/response/error coverage |
| LocalStack fallback | Implemented, unit tested | Transparent non-EMR/Glue forwarding |
| EMR control plane | Partial: 13 boto3-tested operations plus versioned startup-file provisioning through the same use case | Broad public EMR API compatibility |
| EMR bootstrap/Spark | Implemented vertical slice: trusted root pre-start with inventory, final `hadoop` user, S3 bootstrap virtualenv, Python/JAR/dependency materialization, Spark 3.5.4 local S3A write, cancellation, and gzip Step/local-driver LogUri archives | More EMR step types, YARN/executor logs, and distributed runtime fidelity |
| Glue Data Catalog | Partial API inventory: 22 boto3-tested operations with complete deterministic database/table/version/partition/batch errors and opt-in timeout/internal injection | Broader Data Catalog API inventory |
| Spark + Hive + Glue Catalog | Implemented: official Glue 5 image, complex types, typed pruning, partition DDL/repair, supported Hive V1 table ALTER metadata semantics, and deterministic errors for every implemented operation | Broader Spark/Hive client variants |
| Spark + Iceberg + Glue Catalog | Implemented vertical slice: Iceberg 1.7.1 create/append/read, dynamic overwrite, COW/MOR row-level DML, hidden partition/schema/sort/identifier evolution, atomic `VersionId` pointer commit, and concurrent-writer retry E2E | Snapshots/refs/procedures, lifecycle operations, and broader Iceberg APIs |
| AWS SDK for pandas | Implemented vertical slice: 3.17.0 partitioned Parquet S3/Glue write/read E2E | Broader Glue/S3 functions used by this client |
| Service-owned web UIs | Implemented: React/TypeScript EMR cluster/Step/log UI and Glue database/table/schema/partition explorer, shared Tailwind design system, thread/task views, keyboard/browser E2E | Live Spark UI links |

EMR and Glue serve their UIs directly at `/_mystack/ui/`; Proxy exposes them at
`/_mystack/ui/emr/` and `/_mystack/ui/glue/`. The compatibility path `/_mystack/console` redirects
to EMR. Glue metadata mutations use serialized
candidate-state transactions: persistence failure leaves visible and durable state unchanged, and
database/table rename or deletion includes child tables and partitions in one commit. The versioned
JSON document is stored at `glue.state_file`; schema version 1 is migrated on the next mutation.
For Iceberg tables, this transaction now includes inter-process file locking, latest-state reload,
and an atomic `VersionId`/`metadata_location` compare-and-swap. Iceberg still owns data, manifest,
metadata, snapshot, and retry logic; see the [Iceberg commit protocol](protocols/glue-iceberg-commits.md).
The fixed partition, schema, sort, and identifier behavior is recorded separately in the
[Iceberg evolution protocol](protocols/glue-iceberg-evolution.md).
The fixed `INSERT`/`UPDATE`/`DELETE`/`MERGE` behavior and COW/MOR evidence are in the
[Iceberg row-level DML protocol](protocols/glue-iceberg-row-level-dml.md).
`GetPartitions` supports the documented comparison, logical, `IN`,
`BETWEEN`, `LIKE`, and null predicates with typed keys, precedence, paging, and segments. See the
[partition-expression protocol](protocols/glue-partition-expressions.md) for grammar and limits.
Spark Hive partition add/drop/rename/location and repair mappings are documented in the
[Hive partition DDL protocol](protocols/glue-hive-partition-ddl.md).
Supported table-level column/property/SerDe/location changes and client-owned unsupported variants
are documented in the [Hive table ALTER protocol](protocols/glue-hive-table-alter.md).
All implemented operations participate in the generated [Glue error
matrix](compatibility/glue-errors.generated.md); precedence, safe logging, and file-driven failure
injection are defined by the [error decision protocol](protocols/glue-error-decisions.md).
Database/table/version validation, conflict, version, archive, rename, cascade, and rollback behavior
is fixed by the [resource error contract](protocols/glue-database-table-errors.md).
Partition value, list, update, batch order, item error, `UnprocessedKeys`, and rollback behavior is
fixed by the [partition/batch error contract](protocols/glue-partition-batch-errors.md).

Every currently implemented control-plane operation (EMR 13, Glue 22) has public-Proxy boto3
E2E coverage. This is implementation coverage, not a claim that all upstream EMR/Glue operations
are supported; the exact upstream classification is generated from the pinned botocore model.
Startup-file entries accept only the documented allowlist, use `RunJobFlow` member names, and are
recreated with new IDs after EMR process restart. See the [startup cluster protocol](protocols/emr-startup-clusters.md).
Trusted pre-start scripts are an opt-in EMR container boundary, not an in-process plugin API or an
EMR bootstrap action. Exact checks and exclusions are in the [pre-start contract](protocols/emr-prestart.md).

<!-- section: exclusions -->
## Explicit exclusions

- AWS Glue Job and JobRun APIs
- AWS Glue Crawlers
- In-process user extension or plugin APIs
- undocumented AWS bug reproduction
- authentication, authorization, IAM and Lake Formation semantics
- cross-account and cross-Region semantics
- real-AWS comparison tests and cloud credentials
- PyIceberg, Flink, Trino and the Glue Iceberg REST endpoint
- physical EC2/YARN/HDFS distribution fidelity
- Spark History Server

<!-- section: versions -->
## Version baseline

- Python API services: Python 3.11, tested on 3.11 and 3.12
- Protocol model: botocore 1.43.66; tracked by `contracts/service-model-manifest.json`
- Spark: 3.5.x; Glue interoperability profile uses Spark 3.5.4
- Java: 17
- Iceberg: 1.7.1 for the Glue 5.0 profile
- AWS SDK for pandas: 3.17.0

The Glue runtime versions follow [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) and the [official Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html). EMR semantics follow the [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).

Glue type fields are deliberately preserved rather than narrowed because AWS documents that
the [Data Catalog does not validate type strings](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
