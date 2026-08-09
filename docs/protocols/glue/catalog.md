<!-- doc-id: glue-catalog-guide -->
<!-- lang: en -->

[한국어](catalog.ko.md) | [English](catalog.md)

# Glue Catalog guide

<!-- toc:start -->
## Contents

- [Read in this order](#read-in-this-order)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This guide groups the durable Glue Data Catalog behavior behind the public API.

<!-- section: reading-order -->
## Read in this order

1. [SQLite runtime](glue-sqlite-runtime.md) — storage guarantees and runtime limits.
2. [Database and table errors](glue-database-table-errors.md) — catalog validation and failures.
3. [Error decisions](glue-error-decisions.md) — deterministic first-failure precedence.
4. [Partition expressions](glue-partition-expressions.md) — parser and typed filtering behavior.
5. [Batch partition errors](glue-partition-batch-errors.md) — per-item partial-success semantics.
6. [Table optimizers](glue-table-optimizers.md) — supported optimizer control-plane behavior.

Use boto3 contracts under `glue/tests/` for a catalog API change. The full public support claim is
summarized in [`docs/compatibility/api-coverage.md`](../../compatibility/api-coverage.md).

<!-- section: sources -->
## Official sources

- [AWS Glue Data Catalog API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
