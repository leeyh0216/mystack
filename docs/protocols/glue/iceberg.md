<!-- doc-id: glue-iceberg-guide -->
<!-- lang: en -->

[한국어](iceberg.ko.md) | [English](iceberg.md)

# Glue Iceberg guide

<!-- toc:start -->
## Contents

- [Read in this order](#read-in-this-order)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This guide covers the supported Apache Iceberg Java GlueCatalog lifecycle and metadata boundary.

<!-- section: reading-order -->
## Read in this order

1. [Open Table Format](glue-open-table-format.md) — Glue request boundary for Iceberg metadata.
2. [Commits](glue-iceberg-commits.md) — atomic metadata compare-and-swap and retries.
3. [Evolution](glue-iceberg-evolution.md) — schema, partition, and sort evolution.
4. [Row-level DML](glue-iceberg-row-level-dml.md) — COW/MOR write paths.
5. [Snapshots, refs, and procedures](glue-iceberg-snapshots-refs-procedures.md) — query and
   maintenance semantics.
6. [Lifecycle](glue-iceberg-lifecycle.md) — rename, drop, purge, and managed tables.
7. [Table optimizers](glue-table-optimizers.md) — Glue optimizer control-plane operations.

Validate this path with the pinned Apache Iceberg Java GlueCatalog scenario. PyIceberg, Flink,
Trino, and the Glue Iceberg REST endpoint are explicit exclusions.

<!-- section: sources -->
## Official sources

- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
