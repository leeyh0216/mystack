<!-- doc-id: api-coverage -->
<!-- lang: en -->

[한국어](api-coverage.ko.md) | [English](api-coverage.md)

# API compatibility coverage

<!-- toc:start -->
## Contents

- [Overview](#overview)
- [Policy](#policy)
- [Current implemented operations](#current-implemented-operations)
- [Deterministic local error contracts](#deterministic-local-error-contracts)
<!-- toc:end -->

<!-- section: overview -->
## Overview

Compatibility is measured against the pinned botocore service models, not a handwritten operation list.
The service-level API indexes are the [Amazon EMR API operations](https://docs.aws.amazon.com/emr/latest/APIReference/API_Operations.html)
and [AWS Glue Web API operations](https://docs.aws.amazon.com/glue/latest/webapi/API_Operations.html).

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
- Glue catalog: databases, tables, table versions, partitions, batch partition APIs, and table optimizers.

<!-- section: operations -->
## Current implemented operations

The following operations currently have boto3 black-box contracts through a real TCP server.
“Implemented” is not a claim that every optional semantic branch is complete.

| Service | Operations |
| --- | --- |
| EMR | `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, `ListBootstrapActions`, `AddTags`, `RemoveTags`, `SetTerminationProtection`, `SetVisibleToAllUsers` |
| Glue database and table | `CreateDatabase`, `GetDatabase`, `GetDatabases`, `UpdateDatabase`, `DeleteDatabase`, `CreateTable`, `GetTable`, `GetTables`, `UpdateTable`, `DeleteTable`, `GetTableVersion`, `GetTableVersions`, `GetCatalogImportStatus` |
| Glue partitions | `CreatePartition`, `BatchCreatePartition`, `GetPartition`, `GetPartitions`, `BatchGetPartition`, `UpdatePartition`, `BatchUpdatePartition`, `DeletePartition`, `BatchDeletePartition` |
| Glue table optimizers | `CreateTableOptimizer`, `GetTableOptimizer`, `BatchGetTableOptimizer`, `UpdateTableOptimizer`, `DeleteTableOptimizer`, `ListTableOptimizerRuns` |

Documented Glue conflicts are part of the contracts: duplicate single-partition creation
returns HTTP 400 `AlreadyExistsException`, while batch operations return per-item
`ErrorDetail`. See the official [Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
and [Glue exceptions](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html).

The complete machine-generated table is [api-coverage.generated.md](README.md).
It classifies every official operation in the pinned botocore 1.43.66 model: EMR has 13
`COMPATIBLE` and 52 `PROTOCOL_ONLY` operations; Glue has 28 `COMPATIBLE`, 243
`PROTOCOL_ONLY`, and 28 `NOT_PLANNED` operations. `PROTOCOL_ONLY` is not callable support;
it means only that the upstream request/response model is tracked. The Glue `NOT_PLANNED` entries
are Jobs, JobRuns, and Crawlers. The committed JSON baseline stores a status and operation-shape
fingerprint for each entry. A new upstream operation is never assigned a default during `--check`;
it is reported as unclassified and fails CI. Shape changes and removals are reported separately
with adapter, test, and documentation fix hints.

<!-- section: local-errors -->
## Deterministic local error contracts

Mystack does not compare responses with a real AWS account. Each implemented operation records its
documented error conditions, status and response shape from the official API reference and pinned
botocore model. Ambiguous first-failure precedence is an internal reviewed contract. State-triggered
errors use parameterized fixtures; documented service/internal failures use configured fault
injection. IAM, Lake Formation, authentication and authorization errors are not classified as
compatibility targets.

Official operation and shape inventory: [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data). Glue behavior: [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html). EMR behavior: [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).
