<!-- doc-id: docs-index -->
<!-- lang: en -->

[한국어](index.ko.md) | [English](index.md)

# Mystack documentation

<!-- toc:start -->
## Contents

- [Overview](#overview)
- [Getting started](#getting-started)
- [Glue Data Catalog](#glue-data-catalog)
- [Amazon EMR](#amazon-emr)
- [Configuration and operations](#configuration-and-operations)
- [Contributors](#contributors)
- [Official sources](#official-sources)
<!-- toc:end -->

Use this guide to navigate Mystack as an application or data-pipeline developer. Each page starts
with the task it answers and links to deeper technical material only when it is useful.

<!-- section: overview -->
## Overview

Mystack provides a local development environment for Amazon EMR, AWS Glue Data Catalog, Spark, and
LocalStack S3. Start with Docker Compose, then choose Glue or EMR based on the workload you want to
run.

<!-- section: start -->
## Getting started

- [Start Docker Compose and configure AWS CLI or boto3](getting-started.md)
- [Change a published-image deployment](configuration.md)
- [Use the management UI and diagnostics](operations.md)

<!-- section: glue -->
## Glue Data Catalog

- [Use Glue with boto3, AWS SDK for pandas, Spark Hive, and Iceberg](glue.md)
- [Choose a client and follow its Glue/EMR request path](client-workflows.md)
- [Check client and library compatibility](compatibility/client-matrix.md)
- [Check user-facing support boundaries](support-scope.md)
- [Operate the Glue SQLite catalog, verified runtime, and durability policy](protocols/glue/glue-sqlite-runtime.md)

<!-- section: emr -->
## Amazon EMR

- [Create clusters and submit Spark or PySpark Steps](emr.md)
- [Find Step logs and LogUri objects](protocols/emr/emr-log-layout.md)
- [Configure trusted image pre-start actions](protocols/emr/emr-prestart.md)
- [Provision clusters when the container starts](protocols/emr/emr-startup-clusters.md)

<!-- section: operations -->
## Configuration and operations

- [Configuration reference](configuration.md)
- [Management UI, live logs, and diagnostics](operations.md)
- [Structured logging and troubleshooting](observability.md)

<!-- section: contributors -->
## Contributors

Implementation, protocol, architecture, development, testing, CI, and release documentation starts
in the [Contributors guide](maintainers.md). The exhaustive AWS API/endpoint inventory is kept in the
[API compatibility reference](compatibility/api-coverage.md), separate from user support guidance.

<!-- section: sources -->
## Official sources

- [Amazon EMR documentation](https://docs.aws.amazon.com/emr/)
- [AWS Glue documentation](https://docs.aws.amazon.com/glue/)
- [Docker Compose reference](https://docs.docker.com/reference/compose-file/)
