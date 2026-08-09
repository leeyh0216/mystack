<!-- doc-id: protocols-index -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Protocol implementation guide

<!-- toc:start -->
## Contents

- [Read by topic](#read-by-topic)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
These documents describe internal behavior that backs the public AWS-compatible API. They are for
contributors; begin with the service guide and then follow the path relevant to the change.

<!-- section: reading-order -->
## Read by topic

### Glue Data Catalog

Start with the [Glue protocol guide](glue/README.md), then choose one focused path:
[Catalog](glue/catalog.md), [Hive](glue/hive.md), or [Iceberg](glue/iceberg.md).

### Amazon EMR

1. [Startup clusters](emr/emr-startup-clusters.md) — declarative initial provisioning.
2. [Pre-start actions](emr/emr-prestart.md) — trusted container initialization.
3. [Log layout](emr/emr-log-layout.md) — Step logs and `LogUri` objects.

### Shared wire protocol

- [AWS JSON 1.1](aws-json/aws-json-1.1.md) — request validation, operation dispatch, responses, and errors.

When a document refers to a CI-only workload, it is test infrastructure rather than a runtime
feature. Its source and scenario name should be changed with the corresponding `tests/e2e` case.

<!-- section: sources -->
## Official sources

- [AWS JSON protocol reference](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.LowLevelAPI.html)
- [Apache Iceberg documentation](https://iceberg.apache.org/docs/latest/)
