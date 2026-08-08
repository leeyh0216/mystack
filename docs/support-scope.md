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
| Glue Data Catalog | Partial: 22 boto3-tested database/table/version/partition operations | Remaining in-scope Catalog APIs including UDFs |
| Spark + Hive + Glue Catalog | Implemented vertical slice: official Glue 5 image, complex types, S3 Parquet E2E | Broader Hive metadata semantics |
| Spark + Iceberg + Glue Catalog | Implemented vertical slice: Iceberg 1.7.1 create/append/read/schema evolution E2E | Partitions, transactions, and broader Iceberg APIs |
| AWS SDK for pandas | Implemented vertical slice: 3.17.0 partitioned Parquet S3/Glue write/read E2E | Broader Glue/S3 functions and additional clients |
| Web console | Implemented: EMR cluster/Step operations, resumable live logs with pause/resume/download and restart recovery, Glue database/table/schema/partition explorer, route/thread/task views, keyboard/browser E2E | Spark UI and History Server links |

The management console is served at `/_mystack/console`. Glue metadata mutations use serialized
candidate-state transactions: persistence failure leaves visible and durable state unchanged, and
database/table rename or deletion includes child tables and partitions in one commit. The versioned
JSON document is stored at `glue.state_file`; schema version 1 is migrated on the next mutation.
This is Glue Data Catalog metadata transaction behavior, distinct from the Iceberg table-transaction
target in the matrix. The current partition expression evaluator
supports quoted equality and inequality predicates joined by `AND`; unsupported expressions
return `InvalidInputException` instead of silently producing an incorrect result.

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
- production IAM authorization semantics in default local mode
- physical EC2/YARN/HDFS distribution fidelity

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
