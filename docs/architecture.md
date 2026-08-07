# Architecture

## Goals

Mystack emulates EMR and Glue observable behavior at the AWS API boundary while executing real Spark work locally. Protocol compatibility, state transitions, validation, errors, logs, and side effects are first-class contracts.

## System boundaries

| Component | Responsibility | Must not know |
| --- | --- | --- |
| `proxy` | Detect the AWS service and transparently forward the HTTP exchange | EMR/Glue domain rules or persistence |
| `emr` | EMR resources, cluster/step state machines, bootstrap and Spark orchestration | Proxy routing or Glue models |
| `glue` | Glue jobs/runs, Data Catalog, Glue types, Spark/Glue runtime orchestration | Proxy routing or EMR models |
| `shared` | AWS JSON 1.1 codec, official service-model access, request validation primitives | Any EMR/Glue business rule |

Business abstractions are not placed in `shared`. Sharing is limited to the wire protocol boundary.

## Dependency rule

Both emulators use the same inward dependency direction:

```text
domain
  ^
  | implements use cases with ports defined inward
application
  ^
  | adapts HTTP, storage, S3 and processes
adapters
  ^
  | wires concrete dependencies
bootstrap / FastAPI app
```

- Domain: entities, value objects, state machines, domain exceptions, repository port protocols.
- Application: use-case services and orchestration. Depends only on Domain and declared ports.
- Adapters: AWS JSON inbound mapping; SQLite/in-memory, S3, Docker/subprocess and clock/ID outbound implementations.
- Composition root: creates concrete objects and FastAPI routes. No lower module imports it.

Architecture tests reject imports from an inner layer to an outer layer.

## Runtime topology

The public endpoint is the proxy. A single endpoint lets existing CLI/SDK clients use `--endpoint-url` or `AWS_ENDPOINT_URL`; request headers determine the target service. Unknown services are passed to LocalStack.

```text
host:4566 -> proxy:8080
                |-- ElasticMapReduce.* -> emr:8080
                |-- AWSGlue.*          -> glue:8080
                `-- all other traffic  -> localstack:4566
```

The EMR emulator runs one local Spark process at a time per emulated cluster by default. The Glue emulator runs isolated job-run processes and enforces the job's execution/concurrency settings. Runtime processes receive LocalStack endpoints and test credentials through environment variables.

## Compatibility strategy

1. Pin the official AWS SDK service-model version used to define operation names, shapes, enums and declared exceptions.
2. Generate an operation coverage manifest from that model.
3. Test serialization with boto3/AWS CLI against the emulator endpoint.
4. Add semantic contract tests for documented state and error behavior.
5. Where credentials to a real AWS test account are explicitly supplied, run opt-in differential tests with normalized request IDs/timestamps.

“Compatible error” means the documented exception type, HTTP status, error code, relevant message fields, and absence/presence of side effects match. It does not mean reproducing AWS implementation bugs.

## Persistence and execution

- Resource metadata is accessed through repository ports. SQLite is the default durable adapter; an in-memory adapter supports unit tests.
- Work directories and logs are stored on named Docker volumes.
- S3 artifacts are resolved through an object-store port configured for path-style LocalStack access.
- Spark is launched without a shell and receives an explicit argument vector.
- User bootstrap scripts are intentionally executable code and run inside the EMR container boundary, never in the proxy process.

## Non-goals

- Glue Crawlers
- distributed EC2/YARN/HDFS fidelity in the initial runtime
- IAM policy evaluation unless an authentication-enforcement mode is enabled
- reproduction of undocumented AWS bugs

