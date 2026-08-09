# Generated client compatibility matrix

<!-- toc:start -->
## Contents

- [Compatibility cases](#compatibility-cases)
- [Lane policy](#lane-policy)
- [Official sources](#official-sources)
<!-- toc:end -->

This file is deterministically generated from annotated pytest evidence and `contracts/compatibility-scope-policy.yaml`; do not edit it. Each row is one explicit combination run by CI in an isolated process, not an unsupported cross-product.

## Compatibility cases

| Case | Lane | Runtime | Exact versions | Scenarios | Evidence |
| --- | --- | --- | --- | --- | --- |
| `awswrangler-3.17.0-glue-s3` | `required` | `glue-5.0-spark-3.5.4` | awswrangler 3.17.0, boto3 1.43.66, botocore 1.43.66 | parquet-glue-s3-round-trip | `2ca200c2978f172e` |
| `boto3-botocore-1.43.66-contract` | `required` | `python-3.11` | boto3 1.43.66, botocore 1.43.66 | emr-control-plane, glue-data-catalog, modeled-service-errors | `b2acf2470d81cb6b` |
| `boto3-botocore-1.43.66-public-proxy` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66 | glue-operations-through-public-proxy | `19130720ce060698` |
| `emr-7.8.0-spark-3.5.4` | `required` | `emr-7.8.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, emr 7.8.0, spark 3.5.4 | bootstrap-s3-spark-step-lifecycle | `7af9b050b4ac5de8` |
| `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, glue 5.0, iceberg 1.7.1, spark 3.5.4 | hive-complex-types, hive-partition-pruning, hive-partition-ddl-repair, hive-table-alter, iceberg-open-table-format-input, iceberg-create-append-read-evolve, iceberg-partition-schema-sort-evolution, iceberg-row-level-dml, iceberg-snapshots-refs-procedures, iceberg-managed-table-optimizers, iceberg-rename-drop-purge, iceberg-multi-container-contention | `11f660670568d593` |

## Lane policy

- `required`: Must pass before a release can publish.; release_blocking=`true`
- `preview`: Opt-in validation for a proposed client or runtime version.; release_blocking=`false`
- `nightly`: Scheduled evidence for expensive or exploratory combinations.; release_blocking=`false`

## Official sources

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) (`aws-sdk-pandas`)
- [botocore AWS service models](https://github.com/boto/botocore/tree/develop/botocore/data) (`botocore-models`)
- [Amazon EMR 7.8.0 release](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) (`emr-7.8.0`)
- [AWS Glue 5.0 migration guide](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) (`glue-5.0`)
- [AWS Glue Data Catalog as the Spark Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) (`glue-hive`)
- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) (`glue-iceberg`)
- [AWS Glue Open Table Format CreateTable input](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html) (`glue-open-table-format`)
- [AWS Glue Data Catalog table optimizers](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html) (`glue-table-optimizers`)
- [Apache Iceberg 1.7.1 branching and tagging](https://iceberg.apache.org/docs/1.7.1/branching/) (`iceberg-branching`)
- [Apache Iceberg 1.7.1 configuration](https://iceberg.apache.org/docs/1.7.1/configuration/) (`iceberg-configuration`)
- [Apache Iceberg 1.7.1 evolution](https://iceberg.apache.org/docs/1.7.1/evolution/) (`iceberg-evolution`)
- [Apache Iceberg 1.7.1 GlueCatalog implementation](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416) (`iceberg-glue-catalog-source`)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/) (`iceberg-spark-ddl`)
- [Apache Iceberg 1.7.1 Spark procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/) (`iceberg-spark-procedures`)
- [Apache Iceberg 1.7.1 Spark queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/) (`iceberg-spark-queries`)
- [Apache Iceberg 1.7.1 Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/) (`iceberg-spark-writes`)
