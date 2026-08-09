<!-- doc-id: glue-hive-guide -->
<!-- lang: en -->

[한국어](hive.ko.md) | [English](hive.md)

# Glue Hive guide

<!-- toc:start -->
## Contents

- [Read in this order](#read-in-this-order)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This guide covers the Spark SQL path that uses Glue Data Catalog as its Hive metastore.

<!-- section: reading-order -->
## Read in this order

1. [Partition expressions](glue-partition-expressions.md) — typed pruning passed from Spark SQL.
2. [Hive partition DDL](glue-hive-partition-ddl.md) — add/drop/rename/repair behavior.
3. [Hive table ALTER](glue-hive-table-alter.md) — supported metadata mutation variants.
4. [Batch partition errors](glue-partition-batch-errors.md) — Glue control-plane outcomes behind Hive
   metadata operations.

Run the Spark client lab or `tests/e2e/test_glue_spark_catalog.py` after changing this surface. The
runtime path uses the Glue Data Catalog as Spark's Hive metastore; it is not a general Hive
Metastore service.

<!-- section: sources -->
## Official sources

- [AWS Glue Data Catalog as Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
