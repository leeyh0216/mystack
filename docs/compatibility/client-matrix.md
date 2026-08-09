<!-- doc-id: client-compatibility-matrix -->
<!-- lang: en -->

[한국어](client-matrix.ko.md) | [English](client-matrix.md)

# Client and library compatibility

<!-- toc:start -->
## Contents

- [Status levels](#status-levels)
- [Verified clients](#verified-clients)
- [Closed client set](#closed-client-set)
- [Current exclusions](#current-exclusions)
- [Official sources](#official-sources)
<!-- toc:end -->

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

The [test-declared exact-version evidence](annotated-evidence.generated.md) is the authoritative
list used by GitHub Actions. Maintainers add or reuse a typed profile and decorate the smallest
real `contract` or `e2e` test with its tested scenarios and operations. The collection compiler
rejects invalid markers, lock/runtime mismatches, unknown modeled operations, missing supported-API
evidence, and case-selection drift before a test body starts. The retained
[legacy exact-version evidence](client-matrix.generated.md) and `compatibility/cases.yaml` remain
parity baselines during the migration.

| Client | Pinned version | Status | Verified path |
| --- | --- | --- | --- |
| boto3/botocore | 1.43.66 | `CONTRACT`, `E2E` | 13 EMR and 28 Glue Catalog operations plus S3 fixtures |
| AWS SDK for pandas | 3.17.0 | `E2E` | partitioned Parquet write/read, Glue database/table/partition registration and lookup, S3 HEAD |
| Spark Glue Hive client | Glue 5.0 / Spark 3.5.4 | `E2E` | complex-type Parquet table create/insert/read |
| Apache Iceberg Java GlueCatalog | 1.7.1 | `E2E` | create/read/write/evolution, COW/MOR DML, time travel, refs, metadata and maintenance procedures, concurrent retry |

The AWS SDK for pandas case points both `AWS_ENDPOINT_URL_GLUE` and `AWS_ENDPOINT_URL_S3` at the
public Proxy. One scenario covers `wr.catalog.create_database`, `wr.catalog.get_table_types`,
`wr.s3.to_parquet`, `wr.s3.read_parquet`, and boto3 Glue table/partition lookup. It does not imply
support for functions backed by Athena, Redshift, or Lake Formation APIs.

<!-- section: candidates -->
## Closed client set

The compatibility matrix is intentionally limited to boto3/botocore, AWS SDK for pandas, the Spark
Hive client, and the Apache Iceberg Java GlueCatalog. Adding another client requires a future scope
decision; it is not an implied backlog item.

<!-- section: exclusions -->
## Current exclusions

`wr.athena.*`, PyAthena, and dbt-athena require an Athena control plane and query execution, so they
have no current compatibility claim. Passing the AWS SDK for pandas Glue/S3 E2E does not include
these functions. Library paths that require Glue Jobs, JobRuns, or Crawlers are also out of scope.
PyIceberg, Flink, Trino, the Glue Iceberg REST endpoint, cross-account/cross-Region behavior, IAM,
Lake Formation, authentication, and authorization are explicitly outside the compatibility claim.

<!-- section: sources -->
## Official sources

- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [Amazon S3 HeadObject API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
