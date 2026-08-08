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
| EMR control plane | Partial: 13 boto3-tested operations | Broad public EMR API compatibility |
| EMR bootstrap/Spark | Implemented vertical slice: boto3, S3 bootstrap, Python/JAR Spark 3.5.4 local S3A write and running cancellation E2E | More EMR step types and runtime fidelity |
| Glue Data Catalog | Partial: 22 boto3-tested database/table/version/partition operations | Remaining in-scope Catalog APIs including UDFs |
| Glue user extensions | Implemented: stable/application/unsafe v1, mounted wheels, modeled output validation, boto3 contracts | More service contexts and optional remote isolation |
| Spark + Hive + Glue Catalog | Implemented vertical slice: official Glue 5 image, complex types, S3 Parquet E2E | Broader Hive metadata semantics |
| Spark + Iceberg + Glue Catalog | Implemented vertical slice: Iceberg 1.7.1 create/append/read/schema evolution E2E | Partitions, transactions, and broader Iceberg APIs |
| Web console | Implemented: EMR/Glue resources, status/detail, EMR logs, route/thread/task views, keyboard/browser E2E | Additional service-specific visualizations |

The management console is served at `/_mystack/console`. Glue metadata is atomically
persisted to the configured `glue.state_file`. The current partition expression evaluator
supports quoted equality and inequality predicates joined by `AND`; unsupported expressions
return `InvalidInputException` instead of silently producing an incorrect result.

Every currently implemented control-plane operation (EMR 13, Glue 22) has public-Proxy boto3
E2E coverage. This is implementation coverage, not a claim that all upstream EMR/Glue operations
are supported; the exact upstream classification is generated from the pinned botocore model.

<!-- section: exclusions -->
## Explicit exclusions

- AWS Glue Job and JobRun APIs
- AWS Glue Crawlers
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

The Glue runtime versions follow [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) and the [official Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html). EMR semantics follow the [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).

Glue type fields are deliberately preserved rather than narrowed because AWS documents that
the [Data Catalog does not validate type strings](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
