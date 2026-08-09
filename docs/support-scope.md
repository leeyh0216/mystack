<!-- doc-id: support-scope -->
<!-- lang: en -->

[한국어](support-scope.ko.md) | [English](support-scope.md)

# Support scope

<!-- toc:start -->
## Contents

- [Overview](#overview)
- [Explicit exclusions](#explicit-exclusions)
- [Version baseline](#version-baseline)
<!-- toc:end -->

<!-- section: overview -->
## Overview

Use the generated [client compatibility matrix](compatibility/client-matrix.generated.md) for a
compact client-facing feature/version/verification answer. The exhaustive maintainer inventory is
the separate [API coverage reference](compatibility/api-coverage.generated.md).

This document distinguishes implemented behavior from long-term targets. “Target” never means that the current build is already compatible.

| Area | Current status | Target |
| --- | --- | --- |
| Extensible proxy registry | Implemented, unit tested | Any AWS JSON/SigV4 emulator can register without proxy code changes |
| AWS JSON 1.1 codec/model validation | Implemented, unit tested | EMR and Glue modeled request/response/error coverage |
| LocalStack fallback | Implemented, unit tested | Transparent non-EMR/Glue forwarding |
| EMR control plane | Partial: 13 boto3-tested operations plus versioned startup-file provisioning through the same use case | Broad public EMR API compatibility |
| EMR bootstrap/Spark | Implemented vertical slice: trusted root pre-start with inventory, final `hadoop` user, S3 bootstrap virtualenv, Python/JAR/dependency materialization, Spark 3.5.4 local S3A write, cancellation, and gzip Step/local-driver LogUri archives | More EMR step types, YARN/executor logs, and distributed runtime fidelity |
| Glue Data Catalog | Partial API inventory: 28 boto3-tested database/table/version/partition/batch/table-optimizer operations with deterministic errors and opt-in timeout/internal injection | Broader Data Catalog API inventory |
| Spark + Hive + Glue Catalog | Implemented: official Glue 5 image, complex types, typed pruning, partition DDL/repair, supported Hive V1 table ALTER metadata semantics, and deterministic errors for every implemented operation | Broader Spark/Hive client variants |
| Spark + Iceberg + Glue Catalog | Implemented vertical slice: Open Table Format create/update inputs, create/read/write/evolution, COW/MOR DML, time travel, branch/tag writes, principal metadata tables, snapshot/maintenance procedures, managed compaction/retention/orphan-file optimizers, rename/drop/tracked-file purge, S3 cleanup, atomic `VersionId` commits, and concurrent retry | Metadata encryption actions, remaining options/tables, and broader Iceberg APIs |
| AWS SDK for pandas | Implemented vertical slice: 3.17.0 partitioned Parquet S3/Glue write/read E2E | Broader Glue/S3 functions used by this client |
| Service-owned web UIs | Implemented: React/TypeScript EMR cluster/Step/log UI and Glue database/table/schema/partition explorer, shared Tailwind design system, thread/task views, keyboard/browser E2E | Live Spark UI links |

EMR and Glue serve their UIs directly at `/_mystack/ui/`; Proxy exposes them at
`/_mystack/ui/emr/` and `/_mystack/ui/glue/`. The compatibility path `/_mystack/console` redirects
to EMR. Glue metadata mutations use short, normalized SQLite transactions: persistence failure rolls
back the whole mutation, and database/table rename or deletion includes child tables, partitions,
optimizers, and run history atomically. `glue.sqlite.database_file` is the sole durable catalog
store; WAL is the verified default and `rollback` is an explicit development escape hatch. There is
no JSON catalog fallback or migration. For Iceberg tables, the same transaction applies an atomic
`VersionId`/`metadata_location` compare-and-swap. Iceberg still owns data, manifest,
metadata, snapshot, and retry logic; see the [Iceberg commit protocol](protocols/glue/glue-iceberg-commits.md).
The fixed partition, schema, sort, and identifier behavior is recorded separately in the
[Iceberg evolution protocol](protocols/glue/glue-iceberg-evolution.md).
The fixed `INSERT`/`UPDATE`/`DELETE`/`MERGE` behavior and COW/MOR evidence are in the
[Iceberg row-level DML protocol](protocols/glue/glue-iceberg-row-level-dml.md).
Time travel, references, metadata tables, snapshot/maintenance procedures, and S3 cleanup are in
the [Iceberg snapshot/reference/procedure protocol](protocols/glue/glue-iceberg-snapshots-refs-procedures.md).
Rename, catalog-only drop, tracked-file purge, compensation, and cross-Glue/S3 failure boundaries are
in the [Iceberg lifecycle protocol](protocols/glue/glue-iceberg-lifecycle.md).
Service-owned Iceberg v2 metadata materialization for `OpenTableFormatInput` and
`UpdateOpenTableFormatInput`, including S3 compensation and catalog CAS, is defined in the
[Open Table Format input protocol](protocols/glue/glue-open-table-format.md).
Managed optimizer APIs, defaults, scheduling, Spark procedure mapping, errors, logs, and exclusions
are fixed by the [table optimizer protocol](protocols/glue/glue-table-optimizers.md).
`GetPartitions` supports the documented comparison, logical, `IN`,
`BETWEEN`, `LIKE`, and null predicates with typed keys, precedence, paging, and segments. See the
[partition-expression protocol](protocols/glue/glue-partition-expressions.md) for grammar and limits.
Spark Hive partition add/drop/rename/location and repair mappings are documented in the
[Hive partition DDL protocol](protocols/glue/glue-hive-partition-ddl.md).
Supported table-level column/property/SerDe/location changes and client-owned unsupported variants
are documented in the [Hive table ALTER protocol](protocols/glue/glue-hive-table-alter.md).
All implemented operations participate in the generated [Glue error
matrix](compatibility/glue-errors.generated.md); precedence, safe logging, and file-driven failure
injection are defined by the [error decision protocol](protocols/glue/glue-error-decisions.md).
Database/table/version validation, conflict, version, archive, rename, cascade, and rollback behavior
is fixed by the [resource error contract](protocols/glue/glue-database-table-errors.md).
Partition value, list, update, batch order, item error, `UnprocessedKeys`, and rollback behavior is
fixed by the [partition/batch error contract](protocols/glue/glue-partition-batch-errors.md).

Every currently implemented control-plane operation (EMR 13, Glue 28) has public-Proxy boto3
E2E coverage. This is implementation coverage, not a claim that all upstream EMR/Glue operations
are supported; the exact upstream classification is generated from the pinned botocore model.
The generated [release acceptance](compatibility/release-acceptance.generated.md) is the
release-blocking view that joins these API/error contracts with the exact Hive, Iceberg, AWS SDK
for pandas, and EMR PySpark/S3 scenarios from annotated compatibility tests.
Startup-file entries accept only the documented allowlist, use `RunJobFlow` member names, and are
recreated with new IDs after EMR process restart. See the [startup cluster protocol](protocols/emr/emr-startup-clusters.md).
Trusted pre-start scripts are an opt-in EMR container boundary, not an in-process plugin API or an
EMR bootstrap action. Exact checks and exclusions are in the [pre-start contract](protocols/emr/emr-prestart.md).

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
- Open Table Format metadata encryption-key actions
- physical EC2/YARN/HDFS distribution fidelity
- Spark History Server

<!-- section: versions -->
## Version baseline

- Python API services: Python 3.11
- Protocol model: botocore 1.43.66; tracked by `contracts/service-model-manifest.json`
- Spark: 3.5.x; Glue interoperability profile uses Spark 3.5.4
- Java: 17
- Iceberg: 1.7.1 for the Glue 5.0 profile
- AWS SDK for pandas: 3.17.0

The Glue runtime versions follow [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) and the [official Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html). EMR semantics follow the [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).
The published Glue image keeps the Spark/Iceberg catalog path but removes out-of-scope Job, Delta,
Hudi, Flink, streaming, and Redshift assets from that broad development base. It is a trusted local
emulator, not a security boundary; use operator-controlled Glue datasets. Exact expiring scan
decisions and upstream advisories are documented in [container release operations](container-release.md).

Glue type fields are deliberately preserved rather than narrowed because AWS documents that
the [Data Catalog does not validate type strings](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
