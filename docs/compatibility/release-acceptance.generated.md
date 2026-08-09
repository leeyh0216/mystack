[한국어](release-acceptance.ko.generated.md)

# Catalog release acceptance (generated)

<!-- toc:start -->
## Contents

- [Release-blocking guarantees](#release-blocking-guarantees)
- [Explicit exclusions](#explicit-exclusions)
- [Official references](#official-references)
<!-- toc:end -->

This file is deterministically generated from annotated pytest evidence and `contracts/compatibility-scope-policy.yaml`; do not edit it directly. Every case below is `required` and must pass before publication.

Release acceptance is limited to the exact clients, runtimes, operations, and scenarios collected from annotated tests; it is not a claim of complete AWS Glue or EMR compatibility.

Acceptance evidence: `f9e2c10ae1c958e3cec0f57f7259affe1f248b536043c4d2b9ab842638f63e34`

## Release-blocking guarantees

| Area | Claim | Cases | Exact versions | Scenarios | Evidence | Official sources |
| --- | --- | --- | --- | --- | --- | --- |
| `glue-control-plane-errors` — Glue Catalog API and deterministic errors | Every annotated Glue Catalog operation crosses the service boundary, the public Proxy path is exercised, and the documented local error catalog stays exhaustive and ordered. | `boto3-botocore-1.43.66-contract`<br>`boto3-botocore-1.43.66-public-proxy` | boto3 `1.43.66`<br>botocore `1.43.66` | `glue-data-catalog`<br>`modeled-service-errors`<br>`glue-operations-through-public-proxy` | [contracts/api-coverage.generated.json](../../contracts/api-coverage.generated.json)<br>[contracts/glue-error-conditions.yaml](../../contracts/glue-error-conditions.yaml)<br>[docs/compatibility/api-coverage.generated.md](../../docs/compatibility/api-coverage.generated.md)<br>[docs/compatibility/glue-errors.generated.md](../../docs/compatibility/glue-errors.generated.md) | [botocore-models](https://github.com/boto/botocore/tree/develop/botocore/data) |
| `aws-sdk-pandas` — AWS SDK for pandas Glue/S3 round trip | The annotated AWS SDK for pandas profile writes and reads partitioned Parquet while registering and querying Glue database, table, partition, and S3 metadata through the public Proxy. | `awswrangler-3.17.0-glue-s3` | awswrangler `3.17.0`<br>boto3 `1.43.66`<br>botocore `1.43.66` | `parquet-glue-s3-round-trip` | [tests/e2e/test_awswrangler.py](../../tests/e2e/test_awswrangler.py)<br>[docs/compatibility/client-matrix.md](../../docs/compatibility/client-matrix.md) | [aws-sdk-pandas](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html) |
| `spark-hive` — Spark Hive catalog behavior | The annotated Glue 5 Spark Hive client covers complex types, typed partition pruning, partition DDL and repair, and the supported ALTER TABLE metadata variants. | `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | boto3 `1.43.66`<br>botocore `1.43.66`<br>glue `5.0`<br>iceberg `1.7.1`<br>spark `3.5.4` | `hive-complex-types`<br>`hive-partition-pruning`<br>`hive-partition-ddl-repair`<br>`hive-table-alter` | [tests/e2e/test_glue_spark_catalog.py](../../tests/e2e/test_glue_spark_catalog.py)<br>[docs/protocols/glue-partition-expressions.md](../../docs/protocols/glue-partition-expressions.md)<br>[docs/protocols/glue-hive-partition-ddl.md](../../docs/protocols/glue-hive-partition-ddl.md)<br>[docs/protocols/glue-hive-table-alter.md](../../docs/protocols/glue-hive-table-alter.md) | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)<br>[glue-hive](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html) |
| `iceberg` — Iceberg Java GlueCatalog lifecycle | The annotated Glue 5 profile covers Open Table Format input, create/read/write/evolution, row-level DML, snapshots and refs, maintenance procedures, managed optimizers, rename/drop/purge, and concurrent commit retry. | `glue-5.0-spark-3.5.4-hive-iceberg-1.7.1` | boto3 `1.43.66`<br>botocore `1.43.66`<br>glue `5.0`<br>iceberg `1.7.1`<br>spark `3.5.4` | `iceberg-open-table-format-input`<br>`iceberg-create-append-read-evolve`<br>`iceberg-partition-schema-sort-evolution`<br>`iceberg-row-level-dml`<br>`iceberg-snapshots-refs-procedures`<br>`iceberg-managed-table-optimizers`<br>`iceberg-rename-drop-purge`<br>`iceberg-multi-container-contention` | [tests/e2e/test_glue_spark_catalog.py](../../tests/e2e/test_glue_spark_catalog.py)<br>[docs/protocols/glue-open-table-format.md](../../docs/protocols/glue-open-table-format.md)<br>[docs/protocols/glue-iceberg-evolution.md](../../docs/protocols/glue-iceberg-evolution.md)<br>[docs/protocols/glue-iceberg-row-level-dml.md](../../docs/protocols/glue-iceberg-row-level-dml.md)<br>[docs/protocols/glue-iceberg-snapshots-refs-procedures.md](../../docs/protocols/glue-iceberg-snapshots-refs-procedures.md)<br>[docs/protocols/glue-table-optimizers.md](../../docs/protocols/glue-table-optimizers.md)<br>[docs/protocols/glue-iceberg-lifecycle.md](../../docs/protocols/glue-iceberg-lifecycle.md)<br>[docs/protocols/glue-iceberg-commits.md](../../docs/protocols/glue-iceberg-commits.md) | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html)<br>[glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)<br>[glue-open-table-format](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html)<br>[glue-table-optimizers](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html)<br>[iceberg-evolution](https://iceberg.apache.org/docs/1.7.1/evolution/)<br>[iceberg-spark-writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/)<br>[iceberg-configuration](https://iceberg.apache.org/docs/1.7.1/configuration/)<br>[iceberg-spark-queries](https://iceberg.apache.org/docs/1.7.1/spark-queries/)<br>[iceberg-spark-ddl](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)<br>[iceberg-spark-procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/)<br>[iceberg-branching](https://iceberg.apache.org/docs/1.7.1/branching/)<br>[iceberg-glue-catalog-source](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416) |
| `emr-pyspark-s3` — EMR PySpark and LocalStack S3 regression | boto3 creates and controls the emulated EMR cluster while bootstrap actions, S3 artifact download, local PySpark execution, cancellation, lifecycle, and log publication remain functional. | `boto3-botocore-1.43.66-contract`<br>`emr-7.8.0-spark-3.5.4` | boto3 `1.43.66`<br>botocore `1.43.66`<br>emr `7.8.0`<br>spark `3.5.4` | `emr-control-plane`<br>`bootstrap-s3-spark-step-lifecycle` | [emr/tests/test_boto3_contract.py](../../emr/tests/test_boto3_contract.py)<br>[tests/e2e/test_emr_spark.py](../../tests/e2e/test_emr_spark.py)<br>[docs/protocols/emr-log-layout.md](../../docs/protocols/emr-log-layout.md)<br>[docs/testing.md](../../docs/testing.md) | [botocore-models](https://github.com/boto/botocore/tree/develop/botocore/data)<br>[emr-7.8.0](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) |

## Explicit exclusions

| Area | Reason | Official sources |
| --- | --- | --- |
| `glue-compute` — Glue compute services | Jobs, JobRuns, Crawlers, and their client paths are outside this catalog-store release. | [glue-5.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html) |
| `security-and-cloud-boundaries` — Security and cloud account boundaries | Authentication, authorization, IAM, Lake Formation, cross-account, and cross-Region semantics are not emulated. | [glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) |
| `additional-catalog-clients` — Additional catalog clients | PyIceberg, Flink, Trino, and the Glue Iceberg REST endpoint have no compatibility claim. | [glue-iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html) |
| `external-fidelity` — External AWS and distributed runtime fidelity | Real-AWS differential tests and physical EC2, YARN, or HDFS distribution are excluded. | [emr-7.8.0](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html) |

## Official references

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
