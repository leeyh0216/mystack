<!-- doc-id: architecture -->
<!-- lang: en -->

[한국어](architecture.ko.md) | [English](architecture.md)

# Architecture

<!-- section: goals -->
## Goals

Mystack emulates EMR and Glue observable behavior at the AWS API boundary while executing real Spark work locally. Protocol compatibility, state transitions, validation, errors, logs, and side effects are first-class contracts.

<!-- section: boundaries -->
## System boundaries

| Component | Responsibility | Must not know |
| --- | --- | --- |
| `proxy` | Detect the AWS service and transparently forward the HTTP exchange | EMR/Glue domain rules or persistence |
| `emr` | EMR resources, cluster/step state machines, bootstrap and Spark orchestration | Proxy routing or Glue models |
| `glue` | Glue Data Catalog, Glue types, and Hive/Iceberg interoperability | Proxy routing or EMR models |
| `shared` | AWS JSON 1.1 codec, official service-model access, request validation primitives | Any EMR/Glue business rule |

Business abstractions are not placed in `shared`. Sharing is limited to the wire protocol boundary.
Mystack does not expose an in-process user plugin API. Service behavior changes remain inside the
owning bounded context, while new AWS service emulators join through Proxy's configuration-driven
route registry.
The independently built distributions share the implicit `mystack` namespace described in
[ADR-0003](adr/0003-pep420-namespace-packages.md); none owns the namespace root.

<!-- section: dependencies -->
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

Glue's Domain owns normalized `CatalogName`, defensive lossless `CatalogDocument` snapshots,
immutable database/table/partition values, table revision/archive/CAS behavior, and partition value
cardinality. Transport dictionaries are copied on entry and exit, so an adapter or caller cannot
mutate committed aggregate state. This preserves all documented Glue fields while respecting AWS's
statement that the [Data Catalog does not validate type strings](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).

Glue Application responsibilities are separate handlers for database commands/queries, table
commands/queries, table-version queries, partition commands/queries, partial-success partition
batches, pagination, and initialization. `CatalogApplication` is a delegation-only compatibility
facade for inbound ports. Rename and cascade policy belongs to these handlers; repositories expose
only snapshot and candidate-transaction capabilities.

EMR Application separates cluster commands, Step commands, read-only queries, opaque pagination,
queue-completion/failure policy, and the asynchronous cluster driver. The inbound adapter declares
those minimal command/query Protocols instead of depending on the concrete facade. The typed EMR
runtime is built without starting work; FastAPI lifespan starts it and closes scheduler tasks,
bootstrap/Spark child processes, then the S3 artifact client. Close is idempotent, uses the configured
deadline, and removes per-cluster driver locks after each run. This follows Python's documented
[task cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation) and
[async subprocess](https://docs.python.org/3/library/asyncio-subprocess.html) contracts.

Inbound AWS mapping is organized by operation family. EMR owns cluster, Step, control, tag, and
query families; Glue owns database, table, version, partition, and batch families. A shared validated
registry merges them and fails startup on duplicate ownership, a missing implemented operation, or
an unexpected unclassified handler. The registry is checked bidirectionally against the exhaustive
compatibility classification derived from the official [botocore service
models](https://github.com/boto/botocore/tree/develop/botocore/data). Parsing and output-model
validation remain in the single shared AWS JSON endpoint.

<!-- section: enforcement -->
## Executable architecture contract

`make architecture-check` resolves absolute and relative Python imports, builds the internal module
graph, and rejects the following dependency changes before they reach runtime:

| Rule | Rejected dependency |
| --- | --- |
| `shared-service-dependency` | Shared wire code imports an emulator service |
| `proxy-service-dependency` | Proxy imports EMR or Glue instead of using its route registry |
| `cross-service-dependency` | EMR and Glue import each other |
| `outward-dependency` | Domain/Application/Adapter imports a more outward layer |
| `inner-transport-dependency` | Domain or Application imports FastAPI, boto, or another transport |
| `composition-only-adapter` | A non-composition module imports a concrete adapter |
| `adapter-sibling-dependency` | An inbound adapter imports an outbound adapter, or the reverse |
| `inbound-concrete-facade` | An inbound adapter imports a concrete Application facade |
| `service-import-cycle` | Internal modules form a direct or indirect import cycle |

Inbound adapters depend on the minimal Protocols in `application/use_cases.py` and immutable values
in `application/commands.py`. Concrete adapters may be imported and constructed only by
`mystack.emr.app` or `mystack.glue.app`. Imports inside one inbound or outbound adapter package are
allowed; crossing between the two sides is not. Generated JSON and Markdown are outside Python
source roots, and no generated Python file is excluded.

Every prohibited direction has a mutation test that injects a violating source file and proves that
the checker rejects it. A failure reports the source path and line, imported module, rule identifier,
and a repair instruction. The implementation follows Python's [documented relative-import
semantics](https://docs.python.org/3/reference/import.html#package-relative-imports).

<!-- section: topology -->
## Runtime topology

The public endpoint is the proxy. A single endpoint lets existing CLI/SDK clients use `--endpoint-url` or `AWS_ENDPOINT_URL`; request headers determine the target service. Unknown services are passed to LocalStack.

```text
host:4566 -> proxy:8080
                |-- ElasticMapReduce.* -> emr:8080
                |-- AWSGlue.*          -> glue:8080
                `-- all other traffic  -> localstack:4566
```

The EMR emulator runs one local Spark process at a time per emulated cluster by default. Spark-based Glue interoperability tests use versioned runtime profiles; Glue Job/JobRun execution is not implemented. Runtime processes receive LocalStack endpoints and test credentials through environment variables.

Management traffic uses a separate outward read-model boundary. Each service's inbound management
adapter translates its Application/Domain resources to versioned JSON; the Proxy forwards that JSON
and the packaged browser UI renders it without importing service internals. See the
[management console contract](console.md).

Proxy controllers receive only typed AWS-request and management-forwarding capabilities from a
runtime context. The context owns one shared HTTP pool, closes it exactly once on normal shutdown or
partial startup failure, and never exposes the client through FastAPI application state. Route
detection is a Protocol implemented by the configuration-driven detector. This lifecycle follows
HTTPX's [official client guidance](https://www.python-httpx.org/advanced/clients/#opening-and-closing-clients).

<!-- section: compatibility -->
## Compatibility strategy

1. Pin the official AWS SDK service-model version used to define operation names, shapes, enums and declared exceptions.
2. Generate an operation coverage manifest from that model.
3. Test serialization with boto3/AWS CLI against the emulator endpoint.
4. Add semantic contract tests for documented state and error behavior.
5. Where credentials to a real AWS test account are explicitly supplied, run opt-in differential tests with normalized request IDs/timestamps.

“Compatible error” means the documented exception type, HTTP status, error code, relevant message fields, and absence/presence of side effects match. It does not mean reproducing AWS implementation bugs.

<!-- section: logging -->
## Logging

Controllers, routing decisions, state transitions, and side effects emit structured before,
after, and failure events. Logs exclude authorization values and raw request bodies. They include
request IDs, operations, model versions and fingerprints, body lengths or hashes, duration, and
status. Model mismatch events include a `fix_hint` that identifies the adapter and document to
change.

<!-- section: persistence -->
## Persistence and execution

- Glue Application code applies each mutation to an isolated `CatalogState` candidate while the
  repository serializes transactions. The JSON state store persists and fsyncs schema version 2,
  atomically replaces the previous document, and only then publishes the candidate to readers.
  Persistence failure rolls the candidate back, while cancellation during a successful durable
  commit completes visible publication before cancellation is returned. Schema version 1 loads
  read-only and migrates on the next successful mutation.
- Persistence is composed behind the repository transaction; the JSON repository does not inherit
  in-memory mutation behavior. EMR cluster state remains process-local.
- The EMR startup-file adapter validates a complete versioned `RunJobFlow` plan before side effects,
  maps it to `CreateCluster` commands, and calls the existing Application port after the queue driver
  starts. It never knows or mutates the repository. Container restart intentionally creates new
  process-local IDs. See the [startup cluster protocol](protocols/emr-startup-clusters.md).
- Work directories and logs are stored on named Docker volumes.
- A lifecycle-owned outbound log publisher projects terminal local Spark process streams into the
  documented EMR Step S3 layout. Its application/container identifiers are explicitly synthetic;
  publication failure is recorded outside the aggregate and never rewrites the RuntimeResult.
- S3 primary applications and Spark dependency options are materialized through an object-store
  adapter configured for path-style LocalStack access.
- Spark is launched without a shell and receives an explicit argument vector.
- User bootstrap scripts are intentionally executable code and run as `hadoop` with optional `sudo`
  inside the EMR container boundary, never in the proxy process. Files persist across later Steps,
  while shell activation state does not cross subprocess boundaries.
- The optional EMR pre-start entrypoint is a separate trusted deployment boundary outside Domain
  and Application. It validates and sources operator files as root, then a fixed stdlib adapter
  changes groups/GID/UID and execs PID 1 as `hadoop`. No hook object or plugin interface enters the
  service dependency graph. See the [pre-start contract](protocols/emr-prestart.md).

Glue's JSON persistence adapter uses Python's atomic
[`os.replace`](https://docs.python.org/3/library/os.html#os.replace) and durable
[`os.fsync`](https://docs.python.org/3/library/os.html#os.fsync) operations.

<!-- section: non-goals -->
## Non-goals

- Glue Jobs and JobRuns
- Glue Crawlers
- distributed EC2/YARN/HDFS fidelity in the initial runtime
- IAM policy evaluation unless an authentication-enforcement mode is enabled
- reproduction of undocumented AWS bugs

<!-- section: sources -->
## Official references

- [AWS Prescriptive Guidance: Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
- [AWS Prescriptive Guidance: Best practices and CI testing](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)
- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Python language reference: package relative imports](https://docs.python.org/3/reference/import.html#package-relative-imports)
- [Python standard library: fsync](https://docs.python.org/3/library/os.html#os.fsync)
- [AWS Glue types](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)
