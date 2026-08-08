# Generated client compatibility matrix

This file is deterministically generated from `compatibility/cases.yaml`; do not edit it. Each row is one explicit combination run by CI in an isolated process, not an unsupported cross-product.

| Case | Lane | Runtime | Exact versions | Scenarios | Evidence |
| --- | --- | --- | --- | --- | --- |
| `awswrangler-3.17.0-glue-s3` | `required` | `glue-5.0-spark-3.5.4` | awswrangler 3.17.0, boto3 1.43.66, botocore 1.43.66 | parquet-glue-s3-round-trip | `74e5c09a57ec0c32` |
| `boto3-botocore-1.43.66-contract` | `required` | `python-3.11` | boto3 1.43.66, botocore 1.43.66 | emr-control-plane, glue-data-catalog, modeled-service-errors | `e0fc5c4c730c98ad` |
| `boto3-botocore-1.43.66-public-proxy` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66 | glue-operations-through-public-proxy | `debd1c8642816707` |
| `emr-7.8.0-spark-3.5.4` | `required` | `emr-7.8.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, emr 7.8.0, spark 3.5.4 | bootstrap-s3-spark-step-lifecycle | `50b6c4adc782e997` |
| `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | `required` | `glue-5.0-spark-3.5.4` | boto3 1.43.66, botocore 1.43.66, glue 5.0, iceberg 1.7.1, spark 3.5.4 | hive-complex-types, hive-partition-pruning, hive-partition-ddl-repair, hive-table-alter, iceberg-create-append-read-evolve, iceberg-multi-container-contention | `524db84679c2f2ca` |

## Lane policy

- `required`: Must pass before a release can publish.; release_blocking=`true`
- `preview`: Opt-in validation for a proposed client or runtime version.; release_blocking=`false`
- `nightly`: Scheduled evidence for expensive or exploratory combinations.; release_blocking=`false`

## Official sources

- [Amazon Linux public ECR image](https://gallery.ecr.aws/amazonlinux/amazonlinux) (`amazon-linux-image`)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) (`aws-sdk-pandas`)
- [botocore AWS service models](https://github.com/boto/botocore/tree/develop/botocore/data) (`botocore-models`)
- [Docker Compose in CI](https://docs.docker.com/compose/how-tos/ci-cd/) (`docker-compose`)
- [Amazon EMR 7.8.0 release](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) (`emr-7.8.0`)
- [GitHub Actions shared matrices](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations) (`github-matrix`)
- [AWS Glue 5.0 migration guide](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) (`glue-5.0`)
- [AWS Glue Data Catalog as the Spark Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) (`glue-hive`)
- [Using Apache Iceberg with AWS Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) (`glue-iceberg`)
- [AWS Glue libraries public ECR image](https://gallery.ecr.aws/glue/aws-glue-libs) (`glue-libs-image`)
- [Python Package Index file API](https://docs.pypi.org/api/json/) (`pypi-file-api`)
- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html) (`pytest`)
- [Apache Spark downloads and release verification](https://spark.apache.org/downloads.html) (`spark-downloads`)
