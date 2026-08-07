# API compatibility coverage

[한국어](api-coverage.ko.md) | English

Compatibility is measured against the pinned botocore service models, not a handwritten operation list.

| Status | Meaning |
| --- | --- |
| `COMPATIBLE` | Wire shape and documented semantics have contract tests |
| `PARTIAL` | Operation works but one or more documented semantic contracts remain |
| `PROTOCOL_ONLY` | Target/shape is recognized; semantic implementation is pending |
| `NOT_PLANNED` | Explicitly outside project scope |

## Policy

- Every EMR public API operation is a compatibility target.
- Glue Data Catalog public operations are compatibility targets.
- Glue Job, JobRun, and Crawler families are `NOT_PLANNED`.
- The generated coverage report records the pinned model version and fails CI if a new upstream operation has no classification.
- Completing an operation requires positive, validation, not-found/conflict, pagination, idempotency and state-dependent tests where the API documents them.

Initial vertical slices prioritize the APIs needed to execute workloads:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap actions and tags.
- Glue catalog: databases, tables, table versions, partitions, batch partition APIs and user-defined functions.

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

The machine-generated per-operation table will be written to `api-coverage.generated.md` by the service-model coverage tool.

Official operation and shape inventory: [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data). Glue behavior: [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html).
