<!-- doc-id: protocols/glue-error-decisions -->
<!-- lang: en -->

[한국어](glue-error-decisions.ko.md) | [English](glue-error-decisions.md)

# Deterministic Glue error decisions

Mystack defines Glue errors from public API documentation, the pinned botocore model, and internal
catalog invariants. It never queries a live AWS account. The source of truth is
`contracts/glue-error-conditions.yaml`; `scripts/glue_error_contracts.py` requires all 28 implemented
operations to have an ordered contract and generates the [English](../compatibility/glue-errors.generated.md)
and [Korean](../compatibility/glue-errors.ko.generated.md) matrices.

<!-- section: precedence -->
## Decision precedence

The first failing condition stops evaluation in this order:

1. AWS JSON/official operation shape and JSON type
2. Modeled required fields
3. Modeled value constraints
4. Explicit configured fault injection
5. Operation-specific application constraints and parent/resource existence
6. Duplicate or destination conflict
7. Version/concurrency precondition
8. Candidate mutation or ordered batch-item execution
9. Durable persistence side effect

Protocol validation occurs in the shared AWS endpoint before the Glue dispatcher. A valid request
then enters `GlueErrorBoundary`, which applies an optional fault and translates framework-free
domain failures. The repository publishes a candidate only after its durable save succeeds. Batch
item failures are response members and may coexist with earlier successful items; the
[partition/batch contract](glue-partition-batch-errors.md) fixes their complete per-operation semantics.

This is a deterministic Mystack order, not a claim about undocumented AWS evaluation order. The
[database/table/version contract](glue-database-table-errors.md) and
[partition/batch contract](glue-partition-batch-errors.md) fix the resource-specific conditions
without changing the pipeline.

<!-- section: taxonomy -->
## Taxonomy and wire response

| Category | Representative condition | AWS JSON code | Mutation guarantee |
| --- | --- | --- | --- |
| Validation | `protocol.input_shape`, `input.value_invalid` | `InvalidInputException` | Handler not called or candidate not committed |
| Not found | `resource.not_found` | `EntityNotFoundException` | Candidate not committed |
| Conflict | `resource.already_exists` | `AlreadyExistsException` | Candidate not committed |
| Concurrency | `version.mismatch` | `ConcurrentModificationException` | Candidate not committed |
| Injectable | `fault.operation_timeout`, `fault.internal_service` | Configured documented code | Handler not called |
| System | `adapter.mapping_failure`, `persistence.side_effect_failed` | `InternalServiceException` | Candidate not committed/published |

The shared AWS JSON 1.1 controller serializes one shape: `__type`, `Message`, the modeled HTTP
status, `x-amzn-errortype`, and `x-amzn-requestid`. Adapter mapping and persistence messages are
sanitized. Request values and configured fault messages are never written to structured logs.

Authentication, authorization, IAM, Lake Formation, signing rejection, cross-account, and
cross-Region decisions are forbidden. SigV4 metadata may be parsed for routing context but is not a
security boundary.

<!-- section: injection -->
## Reproducible failure injection

Fault injection is off by default and configured only in `glue.fault_injection`. A rule has `id`,
implemented `operation`, documented `error_code`, and response `message`. Supported codes are
`OperationTimeoutException` (HTTP 400) and `InternalServiceException` (HTTP 500). Duplicate rule IDs,
multiple rules for one operation, unknown operations, and authorization errors fail process startup.

Injection is operation-wide and intentionally stateless: every valid matching request fails until
the configuration is disabled and the process restarted. This makes tests reproducible without
hidden counters, request headers, or payload-value matching. Invalid shapes still fail before the
fault, and no application or repository side effect starts.

<!-- section: logging -->
## Logging and maintenance

Every operation-level translated or injected error emits `glue.error.decision` with request/operation/family,
condition ID, category, phase, error code, HTTP status, mutation guarantee, and safe failure type.
The generic dispatcher and controller add model fingerprint, duration, and the final code. Faults
add the rule ID, never its configured message.

When a client upgrade breaks:

1. `protocol.validation.failed` means the pinned botocore input model changed; update shared generic
   shape support or the operation mapping.
2. `adapter.mapping_failure` means the modeled request reached an outdated inbound family; update
   that family, not the repository.
3. A domain condition means the application invariant or its row in the error catalog changed.
4. `persistence.side_effect_failed` means inspect repository transaction before/after logs and the
   mounted state path.
5. Generated drift identifies the operation and condition that must be reviewed.

Run `make glue-errors-generate` after an intentional catalog edit and
`make glue-errors-check` in local/CI verification.

<!-- section: exclusions -->
## Exclusions

The catalog does not reproduce undocumented service bugs, compare with live AWS, inject partial
disk corruption, or provide stochastic/latency-based chaos. Glue Jobs and Crawlers are not
implemented operations and cannot be selected by a rule.

<!-- section: sources -->
## Official sources

- [AWS Glue exceptions](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)
- [AWS Glue Web API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [botocore Glue service model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
- [AWS JSON 1.1 protocol example](https://docs.aws.amazon.com/singlesignon/latest/OIDCAPIReference/Welcome.html)
