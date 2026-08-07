# API compatibility coverage

Compatibility is measured against the pinned botocore service models, not a handwritten operation list.

| Status | Meaning |
| --- | --- |
| `COMPATIBLE` | Wire shape and documented semantics have contract tests |
| `PARTIAL` | Operation works but one or more documented semantic contracts remain |
| `PROTOCOL_ONLY` | Target/shape is recognized; semantic implementation is pending |
| `NOT_PLANNED` | Explicitly outside project scope |

## Policy

- Every EMR public API operation is a compatibility target.
- Every Glue public API operation except the Crawler family is a compatibility target.
- Crawler operations and crawler-specific resources are `NOT_PLANNED`.
- The generated coverage report records the pinned model version and fails CI if a new upstream operation has no classification.
- Completing an operation requires positive, validation, not-found/conflict, pagination, idempotency and state-dependent tests where the API documents them.

Initial vertical slices prioritize the APIs needed to execute workloads:

- EMR: `RunJobFlow`, `DescribeCluster`, `ListClusters`, `AddJobFlowSteps`, `DescribeStep`, `ListSteps`, `CancelSteps`, `TerminateJobFlows`, bootstrap actions and tags.
- Glue jobs: `CreateJob`, `UpdateJob`, `DeleteJob`, `GetJob`, `GetJobs`, `StartJobRun`, `GetJobRun`, `GetJobRuns`, `BatchStopJobRun`.
- Glue catalog: databases, tables, table versions, partitions, batch partition APIs and user-defined functions.

The machine-generated per-operation table will be written to `api-coverage.generated.md` by the service-model coverage tool.

