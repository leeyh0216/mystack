# Generated test-declared compatibility evidence

<!-- toc:start -->
## Contents

- [Official references](#official-references)
<!-- toc:end -->

This document is generated deterministically from pytest `mystack_compatibility` annotations. Each row is a CI case selected by collection without executing test bodies.

| Case | Lane | Runtime | Exact versions | Scenarios | Evidence hash |
| --- | --- | --- | --- | --- | --- |
| `awswrangler-3.17.0-glue-s3` | `required` | `glue-5.0-spark-3.5.4` | awswrangler 3.17.0, boto3 1.43.66, botocore 1.43.66 | parquet-glue-s3-round-trip | `2ca200c2978f172e` |
| `boto3-botocore-1.43.66-contract` | `required` | `python-3.11` | boto3 1.43.66, botocore 1.43.66 | emr-control-plane, glue-data-catalog, modeled-service-errors | `926104be0e0517fc` |
| `boto3-botocore-1.43.66-public-proxy` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66 | glue-operations-through-public-proxy | `19130720ce060698` |
| `emr-7.8.0-spark-3.5.4` | `required` | `emr-7.8.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, emr 7.8.0, spark 3.5.4 | bootstrap-s3-spark-step-lifecycle | `7af9b050b4ac5de8` |
| `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, glue 5.0, iceberg 1.7.1, spark 3.5.4 | hive-complex-types, hive-partition-pruning, hive-partition-ddl-repair, hive-table-alter, iceberg-open-table-format-input, iceberg-create-append-read-evolve, iceberg-partition-schema-sort-evolution, iceberg-row-level-dml, iceberg-snapshots-refs-procedures, iceberg-managed-table-optimizers, iceberg-rename-drop-purge, iceberg-multi-container-contention | `11f660670568d593` |

## Official references

- [official source](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [official source](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html)
- [official source](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [official source](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [official source](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)
- [official source](https://github.com/boto/botocore/tree/develop/botocore/data)
