<!-- doc-id: client-compatibility-matrix -->
<!-- lang: en -->

[한국어](client-matrix.ko.md) | [English](client-matrix.md)

# Client and library compatibility

This document records whether an external AWS-protocol client has actually been verified through
Mystack's single public endpoint. A passing vertical path for one library is never a claim of support
for that library's entire API.

<!-- section: levels -->
## Status levels

| Status | Meaning |
| --- | --- |
| `E2E` | CI runs a data and metadata round trip through the public Proxy and Docker runtime |
| `CONTRACT` | Automated tests verify protocol operations and errors through the public Proxy |
| `CANDIDATE` | An official adapter matches the scope but has no automated evidence yet |
| `OUT_OF_SCOPE` | The path requires an AWS service that Mystack currently excludes |

<!-- section: verified -->
## Verified clients

| Client | Pinned version | Status | Verified path |
| --- | --- | --- | --- |
| boto3/botocore | 1.43.66 | `CONTRACT`, `E2E` | 13 EMR and 22 Glue Catalog operations plus S3 fixtures |
| AWS SDK for pandas | 3.17.0 | `E2E` | partitioned Parquet write/read, Glue database/table/partition registration and lookup, S3 HEAD |
| Spark Glue Hive client | Glue 5.0 / Spark 3.5.4 | `E2E` | complex-type Parquet table create/insert/read |
| Apache Iceberg Java GlueCatalog | 1.7.1 | `E2E` | namespace/table create, append, read, and schema evolution |

The AWS SDK for pandas case points both `AWS_ENDPOINT_URL_GLUE` and `AWS_ENDPOINT_URL_S3` at the
public Proxy. One scenario covers `wr.catalog.create_database`, `wr.catalog.get_table_types`,
`wr.s3.to_parquet`, `wr.s3.read_parquet`, and boto3 Glue table/partition lookup. It does not imply
support for functions backed by Athena, Redshift, or Lake Formation APIs.

<!-- section: candidates -->
## Next verification candidates

| Priority | Client | Value | Recommended layer |
| --- | --- | --- | --- |
| P0 | s3fs/fsspec | lightweight Python coverage of HEAD, Range GET, ListObjectsV2, and multipart boundaries | regular Docker E2E |
| P1 | PyIceberg GlueCatalog | Spark-independent Python Iceberg catalog/file I/O and Glue semantics | regular Docker E2E |
| P2 | Trino Hive/Iceberg connector | independent JVM SQL pressure on Glue metastore, partitions, and statistics | nightly Docker E2E |
| P2 | DuckDB httpfs/Parquet | independent native-client coverage of HEAD, Range GET, glob, and multipart S3 fallback | regular Docker E2E |
| P3 | Flink Iceberg Glue sink | streaming writes, schema propagation, and long-running boundaries | optional nightly E2E |

PyIceberg is the most direct next Glue expansion because it provides Glue as a native catalog type.
Trino deserves a separate profile because its image and startup are heavier and it can call currently
unimplemented surfaces such as statistics APIs. DuckDB and s3fs provide fast regression pressure on
transparent S3 forwarding rather than Glue itself.

<!-- section: exclusions -->
## Current exclusions

`wr.athena.*`, PyAthena, and dbt-athena require an Athena control plane and query execution, so they
have no current compatibility claim. Passing the AWS SDK for pandas Glue/S3 E2E does not include
these functions. Library paths that require Glue Jobs, JobRuns, or Crawlers are also out of scope.

<!-- section: sources -->
## Official sources

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [Amazon S3 HeadObject API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [PyIceberg configuration](https://py.iceberg.apache.org/configuration/)
- [Trino metastore configuration](https://trino.io/docs/current/object-storage/metastores.html)
- [DuckDB S3 API support](https://duckdb.org/docs/current/core_extensions/httpfs/s3api)
- [s3fs documentation](https://s3fs.readthedocs.io/en/latest/)
- [Flink CDC Iceberg Glue example](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.6/docs/connectors/pipeline-connectors/iceberg/)
