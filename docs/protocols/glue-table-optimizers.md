<!-- doc-id: protocols/glue-table-optimizers -->
<!-- lang: en -->

[한국어](glue-table-optimizers.ko.md) | [English](glue-table-optimizers.md)

# Glue managed table optimizer protocol

<!-- section: user-contract -->
## User-visible contract

Mystack implements the six AWS Glue Data Catalog optimizer operations described by the official
[table optimizer API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html):
`CreateTableOptimizer`, `GetTableOptimizer`, `UpdateTableOptimizer`, `DeleteTableOptimizer`,
`BatchGetTableOptimizer`, and `ListTableOptimizerRuns`. Send ordinary boto3 requests to the public
Proxy endpoint. S3 values remain normal `s3://bucket/key` URIs; do not embed the LocalStack HTTP
endpoint in catalog metadata.

```python
glue.create_table_optimizer(
    CatalogId="000000000000",
    DatabaseName="analytics",
    TableName="events",
    Type="compaction",
    TableOptimizerConfiguration={
        "enabled": True,
        "compactionConfiguration": {
            "icebergConfiguration": {
                "strategy": "binpack",
                "minInputFiles": 5,
                "deleteFileThreshold": 1,
            }
        },
    },
)
```

Only Iceberg tables with `Parameters.table_type=ICEBERG` and an absolute
`StorageDescriptor.Location` are eligible. Compaction accepts Parquet tables only, matching the
official [optimizer limitations](https://docs.aws.amazon.com/glue/latest/dg/optimizer-notes.html).
`roleArn` and VPC connection fields are shape-validated and preserved but have no authorization or
network-isolation meaning because IAM and authorization are outside Mystack scope.

<!-- section: defaults -->
## Defaults and validation

The domain normalizes the documented defaults from AWS's [optimizer overview](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html):

| Type | Defaults and bounds |
| --- | --- |
| `compaction` | `binpack`, `minInputFiles=100`, `deleteFileThreshold=1`; four consecutive worker failures disable it |
| `retention` | 5 days, retain 1 snapshot, clean expired files, every 24 hours; interval 3–168 hours |
| `orphan_file_deletion` | 3 days, table location, every 24 hours; interval 3–168 hours; location must be the table path or a real child path |

Modeled shape validation happens before the handler. Table-independent domain values are parsed
into an immutable draft before parent lookup, duplicate conflict, or mutation. Iceberg eligibility,
file format, default location, and location containment are bound after table lookup and before any
mutation. Missing tables/optimizers return `EntityNotFoundException`,
duplicate creates return `AlreadyExistsException`, and invalid type/configuration/location values
return `InvalidInputException`. `BatchGetTableOptimizer` accepts at most 20 entries and returns
per-entry `ErrorDetail` failures. The generated [error matrix](../compatibility/glue-errors.generated.md)
is the executable decision-order inventory. Authentication, authorization, IAM, Lake Formation,
cross-account, and cross-Region branches are deliberately absent.

<!-- section: execution -->
## Scheduler and Spark execution

An enabled optimizer is durably scheduled. One claim moves from `starting` to `in_progress`, then
to `completed` or `failed`; restart recovery turns an abandoned active run into `failed`. Updating,
deleting, or renaming the owning resource is atomic with optimizer state. Update/delete also make
the old worker claim stale, and the scheduler terminates its subprocess. History is bounded by the
configured limit and stored in catalog schema 3.

Each claim starts a bounded Glue 5 `spark-submit` process. The worker uses the official Apache
Iceberg 1.7.1 [Spark procedures](https://iceberg.apache.org/docs/1.7.1/spark-procedures/):

| Optimizer | Execution mapping |
| --- | --- |
| compaction | `rewrite_data_files`; `z-order` resolves identity columns from the current Iceberg sort order and passes Iceberg's documented `sort_order => 'zorder(...)'` argument |
| retention, cleanup enabled | `expire_snapshots` Spark procedure |
| retention, cleanup disabled | Iceberg `ExpireSnapshots.cleanExpiredFiles(false)` Java API, so data files are not deleted |
| orphan deletion | `remove_orphan_files` dry-run candidates, then S3 modification-time filtering and deletion; files created on/before optimizer creation are preserved |

Glue requires an existing Iceberg sort order for both `sort` and `z-order`. The emulator accepts
the API configuration and validates the runtime metadata when a scheduled run starts. A z-order
run without a sort order becomes a diagnostic `failed` run. This release accepts identity sort
fields for z-order; transformed sort fields fail explicitly instead of silently degrading to a
hierarchical sort. The compatibility boundary lives in
`mystack.glue.runtime.table_optimizer_job`.

Per-run `work.json`, `stdout.log`, and `stderr.log` files are written below
`glue.table_optimizers.work_root`. The work file is mode `0600`; payload contents and credentials are
not copied into structured logs. Boundary logs include run ID, optimizer type, timeouts, endpoint
hosts, result metric names, and a repair hint. Timeout causes terminate, then kill after the grace
period for the complete Spark process group. AWS DPU metrics are zero in local mode; file counts, byte counts, duration, and deletion
counts come from the Iceberg result where available.

<!-- section: repair -->
## Configuration and repair locations

All scheduler and process values live under `glue.table_optimizers` in the mounted YAML. See the
[configuration guide](../configuration.md) for the complete block. The dependency direction is:

```text
AWS JSON adapter -> optimizer use cases -> optimizer domain
                                      -> executor port <- Spark subprocess adapter
composition root -> scheduler runtime -> use cases + executor port
```

When an upstream change breaks compatibility, use the structured `fix_hint` and change the narrowest
owner:

- boto3 request/response shape: `adapters/inbound/aws_optimizer.py` and `aws_shapes.py`;
- error selection/order: domain/application plus `contracts/glue-error-conditions.yaml`;
- lifecycle/defaults: `domain/table_optimizer.py`;
- scheduling/cancellation: `application/table_optimizer_runtime.py`;
- Spark command/result decoding: `adapters/outbound/table_optimizer_executor.py`;
- Iceberg procedure or Glue 5 runtime behavior: `runtime/table_optimizer_job.py`;
- durable format: repository schema migration and persistence tests.

Real Glue 5/Spark 3.5.4/LocalStack execution for all three types is CI-only. Local unit tests use a
fake executor and explicit timeouts; the public-Proxy boto3 suite exercises all six APIs.
