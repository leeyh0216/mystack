<!-- doc-id: docs-index -->
<!-- lang: en -->

[한국어](index.ko.md) | [English](index.md)

# User guide

This guide is for people using Mystack to develop applications and data pipelines. If you implement
the repository, protocol, CI, or releases, go to the [maintainer guide](maintainers.md).

<!-- section: start -->
## Start here

1. Follow the [detailed usage guide](getting-started.md) to anonymously pull public GHCR images
   without a source clone, start Docker Compose, and verify the public endpoint.
2. Choose ports, timeouts, data paths, and file overrides in the [configuration guide](configuration.md).
3. Check the exact API and library evidence in the [support scope](support-scope.md) and [client
   compatibility matrix](compatibility/client-matrix.md).

<!-- section: clients -->
## Paths by client

| Client or task | Current evidence | Start with |
| --- | --- | --- |
| AWS CLI and boto3 | 13 EMR and 22 Glue operations through the same public Proxy | [Detailed usage guide](getting-started.md) |
| AWS SDK for pandas 3.17.0 | Partitioned Parquet S3 write/read and Glue table/partitions | [Detailed usage guide](getting-started.md) |
| Spark 3.5.4 Glue Hive client | Complex-type Parquet create/insert/read | [Client compatibility matrix](compatibility/client-matrix.md) |
| Apache Iceberg 1.7.1 GlueCatalog | Namespace/table create, append, read, and schema evolution | [Client compatibility matrix](compatibility/client-matrix.md) |
| EMR Spark step | S3 bootstrap, Python/JAR local Spark, S3A output, and cancellation | [Support scope](support-scope.md) |

An unlisted library or function is not implicitly supported. See [API coverage](compatibility/api-coverage.md)
for operation-by-operation status from the pinned botocore models.

<!-- section: operate -->
## Configure and diagnose usage

- YAML, environment overrides, and Docker mounts: [configuration guide](configuration.md)
- Resource, EMR log, route, and thread/task UI: [management console guide](console.md)
- Structured logs and management endpoints: [observability guide](observability.md)
- EMR `LogUri` S3 object names and local-mode fidelity: [EMR log layout](protocols/emr-log-layout.md)
- Preconfigured clusters and restart semantics: [EMR startup cluster file](protocols/emr-startup-clusters.md)

<!-- section: limits -->
## Know the limits first

Glue Jobs, JobRuns, Crawlers, and Athena query execution are out of scope. Spark/Iceberg and AWS SDK
for pandas are verified only along the paths listed in the compatibility matrix. Mystack does not
reproduce production IAM, EC2/YARN/HDFS distributed environments, or undocumented AWS bugs.

<!-- section: maintainers -->
## When changing the repository

Development setup, architecture, protocol analysis, testing, CI, release, and upstream evolution are
classified only in the [maintainer guide](maintainers.md). User-facing material should be linked here
first; implementation details belong in the maintainer guide.

<!-- section: sources -->
## Official sources

- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Amazon EMR API](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Docker Compose](https://docs.docker.com/reference/compose-file/)
