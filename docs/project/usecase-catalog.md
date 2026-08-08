<!-- doc-id: project-usecase-catalog -->
<!-- lang: en -->

[한국어](usecase-catalog.ko.md) | [English](usecase-catalog.md)

# Implementation-derived UseCase catalog

<!-- section: metadata -->
## Metadata and scope

- Status: approved
- Updated: 2026-08-09
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`
- Included: HTTP endpoints, application operations, runtime processes, management UI, release CLI/workflow
- Excluded: in-process user plugins and Glue Jobs/JobRuns/Crawlers
- Evidence priority: code > tests > commits/issues > documents
- Official inventory: [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data)

<!-- section: uc-001 -->
## UC-001: Route an AWS request

- Purpose/actor/trigger: AWS CLI, boto3, or another SDK sends HTTP to the public Proxy.
- Input: required method/path/body/headers; optional query; YAML route registry. Unique target, signing,
  and host claims are validated at startup.
- Output: backend status, selected safe headers, and raw response bytes; no stored data or events.
- Side effects: exactly one outbound HTTP request to EMR, Glue, or LocalStack.
- Preconditions/rules: target prefix → SigV4 signing service → host prefix → fallback; signed bytes are
  not reserialized.
- Failures: duplicate/invalid routes at startup; connection/explicit request timeout at runtime.
- Observability: route reason, backend origin, body size/hash, status, duration; never authorization/body.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/routing.py:32`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/forwarder.py:57`
- Confidence: High

<!-- section: uc-002 -->
## UC-002: Execute an AWS JSON 1.1 operation

- Purpose/actor/trigger: EMR/Glue inbound endpoint processes an `X-Amz-Target` POST.
- Input: required target and JSON object; optional SigV4 metadata. Pinned operation input shape,
  required/type/enum/pattern constraints are validated before dispatch.
- Output: modeled JSON 200 response or AWS-compatible error body/status/headers.
- Side effects: invokes exactly one explicitly registered built-in handler.
- Preconditions/rules: recognized official operation; unsupported recognized operations return 501.
- Registration rules: each handler belongs to one service-specific family; the registry requires its
  union to equal reviewed implemented coverage exactly before constructing the dispatcher.
- Failures: unknown operation, serialization/validation error, domain error, protected internal error.
- Observability: service/operation/model fingerprint, input/output member names, request ID, duration.
- Evidence: `shared/src/mystack/aws_protocol/endpoint.py`,
  `shared/src/mystack/aws_protocol/operation_registry.py`,
  `emr/src/mystack/emr/adapters/inbound/aws.py`,
  `glue/src/mystack/glue/adapters/inbound/aws.py`
- Confidence: High

<!-- section: uc-003 -->
## UC-003: Manage EMR clusters and steps

- Purpose/actor/trigger: boto3/CLI invokes one of 13 implemented EMR operations through Proxy.
- Input: cluster/step specifications, IDs, markers/page sizes, tag maps, cancellation/termination flags.
  Official shapes plus state invariants and marker format are validated.
- Output: cluster/step descriptions and lists, IDs, cancellation statuses, or empty modeled responses.
- Stored/changed data: process-local clusters, steps, tags, protection/visibility state and timestamps.
- Side effects: schedules asynchronous cluster bootstrap/step driver; cancellation/termination may stop
  child processes.
- Preconditions/rules: documented cluster/step transitions, failure actions, single-cluster queue policy.
- Failures: validation, not found, invalid state, termination protection, bad marker.
- Observability: transitions, scheduling, process lifecycle, public boto3 contract and E2E.
- Responsibility: cluster commands, Step commands, and queries use independent minimal ports;
  only the queue driver owns asynchronous runners and scheduling.
- Evidence: `emr/src/mystack/emr/application/cluster.py`,
  `emr/src/mystack/emr/application/step.py`, `emr/src/mystack/emr/application/queries.py`,
  `emr/src/mystack/emr/application/driver.py`
- Confidence: High

<!-- section: uc-004 -->
## UC-004: Materialize bootstrap/Spark artifacts and execute locally

- Purpose/actor/trigger: EMR background driver starts bootstrap actions or a submitted Spark step.
- Input: S3/local URI, explicit argument vector, cluster/step IDs, LocalStack endpoint/credentials,
  Spark/JAR/Python configuration and runtime timeouts.
- Output: runtime exit code/reason plus stdout/stderr log files; Spark may write LocalStack S3 objects.
- Stored/changed data: work/log directories and EMR state transitions.
- Side effects: S3 downloads and subprocess start/signal/kill/cleanup, always without a shell.
- Preconditions/rules: allowed URI/scheme and step runner; cancellation is idempotent, including pre-start.
  Runtime Build performs no background work; Start enables scheduling; Close cancels and awaits tasks
  and children before closing artifacts with a configured deadline.
- Failures: missing artifact, bootstrap failure, process timeout/exit, cancellation, invalid application args.
- Observability: S3/process before/after/failure events; Python and JAR Spark S3A/cancel E2E.
- Evidence: `emr/src/mystack/emr/runtime.py`,
  `emr/src/mystack/emr/adapters/outbound/runtime.py`,
  `emr/src/mystack/emr/adapters/outbound/system.py`
- Confidence: High

<!-- section: uc-005 -->
## UC-005: Manage Glue databases

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeleteDatabase or import status.
- Input: CatalogId, name, DatabaseInput, pagination token/page size; official shape and normalized non-empty
  name rules.
- Output: modeled database documents/list/next token or empty response.
- Stored/changed data: JSON-backed database record; optional default database on initialization.
- Responsibility: `CatalogDatabase` owns normalized name and defensive document snapshots;
  `DatabaseCommands`, `DatabaseQueries`, and `CatalogInitializer` own separate flows.
- Side effects: persist/fsync/atomic replacement followed by visible candidate publication.
- Preconditions/rules: case-normalized keys, uniqueness, child constraints, serialized candidate
  transaction, and bounded pagination.
- Failures: AlreadyExists, EntityNotFound, InvalidInput and invalid pagination token.
- Observability: transaction/persist before, after, rollback and migration events; direct/public boto3
  tests plus injected failure/cancellation/restart tests.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/outbound/repository.py`
- Confidence: High

<!-- section: uc-006 -->
## UC-006: Manage Glue tables and versions

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeleteTable or GetTableVersion(s).
- Input: CatalogId, database/name, TableInput, expression/attributes, VersionId, SkipArchive and pagination.
- Output: table/version documents, lists/next token, or empty modeled response.
- Stored/changed data: current table, monotonically incremented version and optional archive.
- Responsibility: `CatalogTable` owns revision/archive/CAS; table command, query, and version-query
  handlers are independent.
- Side effects: one candidate commit for table rename, archived version, and child partition keys.
  Iceberg updates atomically swap the supplied `metadata_location`; Mystack does not implement or
  parse the Iceberg metadata format.
- Preconditions/rules: database exists, unique normalized name, optimistic version/archive behavior;
  JSON-backed processes sharing a state file also share one configured bounded POSIX lock.
- Failures: AlreadyExists, EntityNotFound, InvalidInput, and a domain version mismatch translated to
  modeled `ConcurrentModificationException`; open-table-format input excluded.
- Observability: safe Iceberg commit/version/conflict/persistence events, spawned-process CAS tests,
  and two-container real Spark/Iceberg retry E2E.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/tests/test_iceberg_commit.py`, `docs/protocols/glue-iceberg-commits.md`
- Confidence: High

<!-- section: uc-007 -->
## UC-007: Manage Glue partitions and batch results

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeletePartition or four batch operations.
- Input: Catalog/database/table, partition values/input, expression, segment, pagination and schema flags.
- Output: partition/list/batch documents; mutation batch errors are per-entry while missing parents
  and invalid `BatchGetPartition` cardinality fail the whole call. Missing valid get keys are returned
  through `UnprocessedKeys`.
- Stored/changed data: partition records keyed by catalog/database/table/value tuple.
- Responsibility: `CatalogPartition` owns immutable values and cardinality; command, query, and
  partial-success batch handlers are independent.
- Side effects: atomic candidate persistence and publication after each successful entry mutation.
- Preconditions/rules: table preflight; value count equals partition-key count; supported
  predicate/segment; stable input-order processing; Spark Hive rename uses the AWS-maintained Glue
  client `UpdatePartition` path.
- Failures: AlreadyExists, EntityNotFound, InvalidInput and per-item ErrorDetail.
- Observability: safe batch before/item/after and expression phase logs, focused deterministic wire
  contracts, and all 22 Glue operations through public Proxy E2E.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/inbound/aws.py`,
  `docs/protocols/glue-partition-batch-errors.md`
- Confidence: High

<!-- section: uc-008 -->
## UC-008: Inspect service resources and EMR logs

- Purpose/actor/trigger: operator/service-owned UI calls versioned management endpoints directly or through Proxy.
- Input: component/path, resource/log query and configured page limit; there is deliberately no management credential.
- Output: EMR cluster/step/log read models or Glue database/table/partition tree.
- Stored/changed data/events: none; management access audit event.
- Side effects: Proxy makes one internal management HTTP call when the public gateway path is used. Submitted and resolved Step argument vectors are deliberately exposed to this unauthenticated local UI but their values are not emitted in structured logs.
- Preconditions/rules: known component, enabled endpoint, application API pagination, and trusted local-network deployment.
- Failures: disabled endpoint, unknown component/resource, or internal service timeout.
- Observability: management forwarding and component adapter boundary logs plus UI E2E.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/app.py:122`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack/emr/app.py:134`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack/glue/app.py:120`
- Confidence: High

<!-- section: uc-009 -->
## UC-009: Inspect thread/task stacks

- Purpose/actor/trigger: operator/UI calls `/_mystack/diagnostics/threads` or `/tasks`.
- Input: diagnostic kind and configured stack-frame limit; there is deliberately no authentication input.
- Output: thread/task metadata and source stack lines, never frame locals.
- Stored/changed data/events: no resource mutation; diagnostic access audit log.
- Preconditions/rules: diagnostics enabled and trusted local-network deployment.
- Failures: disabled or unknown diagnostic kind.
- Observability: access result, component, client, and explicit `authentication=disabled-by-design` evidence.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack/aws_protocol/diagnostics.py:55`
- Confidence: High

<!-- section: uc-010 -->
## UC-010: Operate the browser management console

- Purpose/actor/trigger: local operator opens `/_mystack/ui/emr/` or `/_mystack/ui/glue/` through Proxy, or `/_mystack/ui/` on an emulator directly.
- Input: cluster/Step forms and actions, database/table/tab selection, refresh, and log-stream controls.
- Output: accessible lifecycle/status, logs and publication evidence, Glue schema/partition metadata, route and stack views.
- Stored/changed data/events: browser selection state; reads use management endpoints while EMR mutations use the public AWS endpoint and normal application use cases.
- Preconditions/rules: each emulator packages its own React/TypeScript application; Proxy only forwards stable paths; shared primitives and Tailwind semantic tokens flow inward; configured polling interval; keyboard/ARIA tab contract; arrays are never shell-parsed.
- Failures: unavailable component/endpoint or modeled AWS error displays a non-secret error with AWS code/request ID when present.
- Observability: Playwright cluster/Step/Glue/keyboard/browser E2E, protocol boundary logs, and captured screenshot.
- Evidence: `ui/src/components.tsx`, `emr/ui/src/App.tsx`, `glue/ui/src/App.tsx`,
  `proxy/src/mystack/proxy/forwarder.py`, `tests/e2e/test_console_browser.py`
- Confidence: High

<!-- section: uc-011 -->
## UC-011: Publish and verify public multi-platform images

- Purpose/actor/trigger: maintainer pushes a semantic tag or manually dispatches GHCR publication.
- Input: component/version plus file-configured packages, Dockerfiles, platforms, Trivy version/policy and
  explicit timeouts.
- Output: anonymously pullable public GHCR tags/digests, BuildKit SBOM/provenance, raw OCI index and
  scan/release artifacts.
- Stored/changed data: GHCR packages and GitHub workflow artifacts.
- Side effects: publisher token login, image build/push/pull, scanner DB/image downloads, and the
  one-time manual package visibility transition.
- Preconditions/rules: ephemeral publisher `GITHUB_TOKEN`, public consumer visibility, new tag,
  amd64+arm64 index; never `latest`.
- Failures: permission/tag collision, build/push, platform verification, timeout or vulnerability policy.
- Observability: registry before/after/failure events and uploaded evidence.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/.github/workflows/container-publish.yml:1`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/scripts/registry_release.py:75`
- Confidence: High for implementation; first complete remote three-package run not yet confirmed.

<!-- section: uc-012 -->
## UC-012: Round-trip data and metadata with AWS SDK for pandas

- Purpose/actor/trigger: a Python application uses AWS SDK for pandas 3.17.0 to manage an S3 Parquet
  dataset and Glue Catalog metadata together.
- Input: DataFrame, S3 dataset URI, database/table names, partition columns, and a boto3 session.
- Output: written object paths, Glue types/table/partitions, and the restored DataFrame.
- Stored/changed data: partitioned Parquet objects in LocalStack S3 and a database/table/partitions in
  the Glue emulator.
- Side effects: sends every S3 and Glue call through one public Proxy endpoint.
- Preconditions/rules: `AWS_ENDPOINT_URL_S3` and `AWS_ENDPOINT_URL_GLUE` point at the same Proxy; the
  Proxy preserves representation `Content-Length` from `HeadObject`.
- Failures: lost S3 metadata, unsupported Glue operation, corrupt Parquet data, or explicit E2E timeout.
- Observability: Proxy route/forward before/after/failure events and Glue operation/repository events;
  the test cleans up created resources.
- Verification: writes and reads two partitions, then checks Glue table types and partitions plus S3
  [HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html).
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/tests/e2e/test_awswrangler.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/forwarder.py`
- Confidence: High

<!-- section: uc-013 -->
## UC-013: Reproduce a documented Glue timeout or internal failure

- Purpose/actor/trigger: maintainer enables a YAML fault rule before starting the Glue emulator and
  sends an otherwise valid boto3/CLI request for that operation.
- Input: unique rule ID, one of 22 implemented operations, `OperationTimeoutException` or
  `InternalServiceException`, and response message.
- Output: modeled AWS JSON error with deterministic code/status/message and request ID.
- Stored/changed data: none; the handler and catalog repository are not called.
- Responsibility: typed application policy contains configuration values; inbound
  `GlueFaultInjector` selects a rule; shared controller owns wire serialization.
- Side effects: none after configuration loading.
- Preconditions/rules: official shape/value validation precedes injection; one rule per operation;
  authentication/authorization errors and unknown operations are rejected at startup.
- Failures: invalid configuration prevents service startup; a nonmatching operation follows its
  natural catalog path.
- Observability: `glue.error.decision` records condition/rule/phase/code and mutation guarantee
  without request values or configured response message.
- Evidence: `contracts/glue-error-conditions.yaml`,
  `glue/src/mystack/glue/adapters/inbound/aws_faults.py`,
  `glue/tests/test_error_contracts.py`
- Confidence: High

<!-- section: uc-014 -->
## UC-014: Apply a deterministic Glue catalog error decision

- Purpose/actor/trigger: a boto3, Spark, or AWS SDK for pandas client performs one of the implemented
  database, table, table-version, or import-status operations.
- Input: official modeled request plus current local catalog state; optional version, projection,
  pagination, archive, and configured fault values.
- Output: success document or the first deterministic modeled validation/not-found/conflict/
  concurrency/system error.
- Stored/changed data: a successful mutation commits one new catalog revision; every failed
  candidate preserves visible and durable snapshots.
- Responsibility: inbound families validate wire-specific projections; application aggregates own
  resource order/archive/rename/cascade; repository owns atomic persistence; error boundary owns code.
- Side effects: durable save only for a successful mutation; queries and natural failures are read-only.
- Preconditions/rules: input before lookup, parent before destination conflict, conflict before stale
  version, durable commit before publication; authentication and external federation states excluded.
- Failures: `InvalidInputException`, `EntityNotFoundException`, `AlreadyExistsException`,
  `ConcurrentModificationException`, or sanitized/configured system errors.
- Observability: operation boundary, condition ID, mutation guarantee, transaction rollback, and
  persistence before/after/failure events without request values.
- Evidence: `docs/protocols/glue-database-table-errors.md`,
  `glue/tests/test_database_table_error_semantics.py`,
  `contracts/glue-error-conditions.yaml`
- Confidence: High
