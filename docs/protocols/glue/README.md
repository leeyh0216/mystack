<!-- doc-id: glue-protocol-index -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Glue protocol guide

<!-- toc:start -->
## Contents

- [Choose a topic](#choose-a-topic)
- [Change checklist](#change-checklist)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: overview -->
This is the contributor entry point for the Glue-compatible catalog service. Choose the topic that
matches the behavior you are changing; each guide gives an ordered path through the detailed design
documents and the associated test boundary.

<!-- section: topic -->
## Choose a topic

| If you are changing… | Read this guide first | Test boundary |
| --- | --- | --- |
| Catalog persistence, database/table behavior, modeled errors, or partitions | [Catalog](catalog.md) | `glue/tests/` boto3 contracts |
| Spark SQL Hive metastore discovery, partition DDL, repair, or ALTER TABLE metadata | [Hive](hive.md) | `tests/e2e/test_glue_spark_catalog.py` |
| Iceberg GlueCatalog metadata, commits, evolution, DML, refs, lifecycle, or optimizers | [Iceberg](iceberg.md) | `tests/e2e/test_glue_spark_catalog.py` |

<!-- section: checklist -->
## Change checklist

1. Change the smallest service component and its black-box or E2E test together.
2. Update the matching topic document when behavior or an exclusion changes.
3. Run `make compatibility-check`; run the relevant Compose client lab for a runtime change.
4. Glue Jobs, JobRuns, Crawlers, IAM, and Lake Formation are explicit scope exclusions.

<!-- section: sources -->
## Official sources

- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
