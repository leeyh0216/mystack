<!-- doc-id: api-coverage -->
<!-- lang: en -->

[한국어](api-coverage.ko.md) | [English](api-coverage.md)

# API compatibility coverage

<!-- section: overview -->
## Overview

Compatibility is measured against the pinned botocore service models, not a handwritten operation list.

| Status | Meaning |
| --- | --- |
| `COMPATIBLE` | Wire shape and documented semantics have contract tests |
| `PARTIAL` | Operation works but one or more documented semantic contracts remain |
| `PROTOCOL_ONLY` | Target/shape is recognized; semantic implementation is pending |
| `NOT_PLANNED` | Explicitly outside project scope |

<!-- section: policy -->
## Policy

- Every EMR public API operation is a compatibility target.
- Glue Data Catalog public operations are compatibility targets.
- Glue Job, JobRun, and Crawler families are `NOT_PLANNED`.
- The generated coverage report records the pinned model version and fails CI if a new upstream operation has no classification.
- Completing an operation requires positive, validation, not-found/conflict, pagination, idempotency and state-dependent tests where the API documents them.

Initial vertical slices prioritize the APIs needed to execute workloads:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap actions and tags.
- Glue catalog: databases, tables, table versions, partitions, batch partition APIs and user-defined functions.

<!-- section: operations -->
## Implemented operations

The following operations currently have boto3 black-box contracts through a real TCP server.
“Implemented” is not a claim that every optional semantic branch is complete.

| Service | Operations |
| --- | --- |
| EMR | `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, `ListBootstrapActions`, `AddTags`, `RemoveTags`, `SetTerminationProtection`, `SetVisibleToAllUsers` |
| Glue | `CreateDatabase`, `GetDatabase`, `GetDatabases`, `UpdateDatabase`, `DeleteDatabase`, `CreateTable`, `GetTable`, `GetTables`, `UpdateTable`, `DeleteTable`, `GetTableVersion`, `GetTableVersions`, `CreatePartition`, `BatchCreatePartition`, `GetPartition`, `GetPartitions`, `BatchGetPartition`, `UpdatePartition`, `BatchUpdatePartition`, `DeletePartition`, `BatchDeletePartition`, `GetCatalogImportStatus` |

Documented Glue conflicts are part of the contracts: duplicate single-partition creation
returns HTTP 400 `AlreadyExistsException`, while batch operations return per-item
`ErrorDetail`. See the official [Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
and [Glue exceptions](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html).

The complete machine-generated table is [api-coverage.generated.md](api-coverage.generated.md).
It contains all 65 EMR and 299 Glue operations in botocore 1.43.66. The committed JSON baseline
stores a status and operation-shape fingerprint for each entry. A new upstream operation is never
assigned a default during `--check`; it is reported as unclassified and fails CI. Shape changes and
removals are reported separately with adapter, test, and documentation fix hints.

<!-- section: differential -->
## Optional real-AWS differential contracts

`contracts/differential-cases.json` defines read-only calls, normalization rules, region, endpoint,
and SDK timeout. Tests are skipped by default and enabled only with
`MYSTACK_REAL_AWS_DIFFERENTIAL=1`; local contributors never need AWS credentials. boto3 resolves
real credentials through its official [credential provider chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html),
while the emulator client receives separate local credentials. Current cases compare the
normalized success envelope of EMR `ListClusters` and Glue `GetCatalogImportStatus`.

Official operation and shape inventory: [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data). Glue behavior: [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html).
