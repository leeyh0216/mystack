<!-- doc-id: project-usecase-catalog -->
<!-- lang: en -->

[한국어](usecase-catalog.ko.md) | [English](usecase-catalog.md)

# Implementation-derived UseCase catalog

<!-- toc:start -->
## Contents

- [Metadata and scope](#metadata-and-scope)
- [UC-001: Route an AWS request](#uc-001-route-an-aws-request)
- [UC-002: Execute an AWS JSON 1.1 operation](#uc-002-execute-an-aws-json-11-operation)
- [UC-003: Manage EMR clusters and steps](#uc-003-manage-emr-clusters-and-steps)
- [UC-004: Materialize bootstrap/Spark artifacts and execute locally](#uc-004-materialize-bootstrapspark-artifacts-and-execute-locally)
- [UC-005: Manage Glue databases](#uc-005-manage-glue-databases)
- [UC-006: Manage Glue tables and versions](#uc-006-manage-glue-tables-and-versions)
- [UC-007: Manage Glue partitions and batch results](#uc-007-manage-glue-partitions-and-batch-results)
- [UC-008: Inspect service resources and EMR logs](#uc-008-inspect-service-resources-and-emr-logs)
- [UC-009: Inspect thread/task stacks](#uc-009-inspect-threadtask-stacks)
- [UC-010: Operate the browser management console](#uc-010-operate-the-browser-management-console)
- [UC-011: Publish and verify public multi-platform images](#uc-011-publish-and-verify-public-multi-platform-images)
- [UC-012: Round-trip data and metadata with AWS SDK for pandas](#uc-012-round-trip-data-and-metadata-with-aws-sdk-for-pandas)
- [UC-013: Reproduce a documented Glue timeout or internal failure](#uc-013-reproduce-a-documented-glue-timeout-or-internal-failure)
- [UC-014: Apply a deterministic Glue catalog error decision](#uc-014-apply-a-deterministic-glue-catalog-error-decision)
- [UC-015: Manage and execute Glue Iceberg table optimizers](#uc-015-manage-and-execute-glue-iceberg-table-optimizers)
- [UC-016: Generate test-declared compatibility evidence](#uc-016-generate-test-declared-compatibility-evidence)
- [Candidate gap: User documentation and contributor evidence](#candidate-gap-user-documentation-and-contributor-evidence)
<!-- toc:end -->

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
- Stored/changed data: normalized SQLite database record; optional default database on initialization.
- Responsibility: `CatalogDatabase` owns normalized name and defensive document snapshots;
  `DatabaseCommands`, `DatabaseQueries`, and `CatalogInitializer` own separate flows.
- Side effects: bounded SQLite transaction commit and durable catalog publication.
- Preconditions/rules: case-normalized keys, uniqueness, child constraints, serialized candidate
  transaction, and bounded pagination.
- Failures: AlreadyExists, EntityNotFound, InvalidInput and invalid pagination token.
- Observability: SQLite transaction/schema before, after, rollback and retry events; direct/public boto3
  tests plus injected failure/cancellation/restart tests.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/outbound/sqlite_catalog/repository.py`
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
  Normal GlueCatalog updates atomically swap the supplied `metadata_location`; Mystack does not
  parse or rewrite client-owned Iceberg metadata. For the distinct official Open Table Format input,
  Mystack materializes an Iceberg v2 metadata candidate through a storage port, then publishes it
  with catalog CAS and compensation. Real-client E2E proves Iceberg-owned partition/schema/sort/
  identifier evolution, COW/MOR row-level commits, refs, snapshot/maintenance procedure commits,
  and rename/drop/purge survive this lossless pointer path and Iceberg-owned lifecycle sequence.
- Preconditions/rules: database exists, unique normalized name, optimistic version/archive behavior;
  one normalized SQLite catalog applies configured busy timeouts and bounded writer retries.
- Failures: AlreadyExists, EntityNotFound, InvalidInput, and a domain version mismatch translated to
  modeled `ConcurrentModificationException`; invalid Open Table Format documents use the same
  deterministic `InvalidInputException` boundary.
- Observability: safe Iceberg commit/version/conflict/persistence events, spawned-process CAS tests,
  COW/MOR snapshot evidence, snapshot/ref/procedure and lifecycle evidence, and two-container real
  Spark/Iceberg retry E2E.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/tests/test_iceberg_commit.py`, `glue/tests/test_iceberg_evolution_catalog.py`,
  `glue/tests/test_iceberg_row_level_catalog.py`,
  `glue/tests/test_iceberg_snapshot_ref_catalog.py`,
  `glue/tests/test_iceberg_lifecycle_catalog.py`,
  `glue/tests/test_open_table_format.py`,
  `docs/protocols/glue/glue-iceberg-snapshots-refs-procedures.md`,
  `docs/protocols/glue/glue-iceberg-lifecycle.md`,
  `docs/protocols/glue/glue-open-table-format.md`
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
  contracts, and all 28 Glue operations through public Proxy E2E.
- Evidence: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/inbound/aws.py`,
  `docs/protocols/glue/glue-partition-batch-errors.md`
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

- Purpose/actor/trigger: a successful direct `develop` or `main` CI run authorizes post-CI
  publication for its exact SHA.
- Input: root `VERSION`, branch/event policy, file-configured packages, Dockerfiles, platforms,
  Trivy policy, and explicit timeouts.
- Output: immutable GHCR tags/digests, BuildKit SBOM/provenance, raw OCI index, and scan/release
  artifacts. Anonymous public pulls become available only after the one-time package-visibility
  transition.
- Stored/changed data: GHCR packages, workflow artifacts, and for stable main releases an annotated
  Git tag plus GitHub Release.
- Side effects: publisher token login, image build/push/pull, scanner DB/image downloads, and the
  one-time manual package visibility transition.
- Preconditions/rules: successful exact-SHA `CI`, allowed source event/branch, same-SHA immutable
  retry, ephemeral `GITHUB_TOKEN`, public consumer visibility, amd64+arm64 index; never `latest`.
- Failures: version drift/non-increment, another-SHA binding, permission, build/push, anonymous
  platform verification, timeout, or vulnerability policy.
- Observability: registry before/after/failure events and uploaded evidence.
- Evidence: `.github/workflows/release.yml`, `.github/workflows/container-publish.yml`,
  `scripts/release/release_policy.py`, `scripts/release/github_release.py`, `scripts/release/registry_release.py`
- Confidence: High for deterministic policy and transaction tests; remote publication remains
  subject to GitHub runner and package visibility state.

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
- Input: unique rule ID, one of 28 implemented operations, `OperationTimeoutException` or
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
- Evidence: `docs/protocols/glue/glue-database-table-errors.md`,
  `glue/tests/test_database_table_error_semantics.py`,
  `contracts/glue-error-conditions.yaml`
- Confidence: High

<!-- section: uc-015 -->
## UC-015: Manage and execute Glue Iceberg table optimizers

- Purpose/actor/trigger: boto3 manages one compaction, retention, or orphan-file optimizer and the
  service scheduler claims a due run.
- Input: catalog/database/table/type, official `TableOptimizerConfiguration`, pagination, and
  file-configured scheduler/process limits.
- Output: six AWS API responses, partial batch failures, bounded run history, typed metrics, and
  per-run Spark stdout/stderr.
- Stored/changed data: optimizer configuration, revision, next-run time, consecutive failures, and
  run history inside catalog schema 3; Iceberg procedures may commit metadata and change LocalStack
  S3 objects.
- Responsibility: optimizer domain owns defaults and transitions; application command/query
  handlers own aggregate mutation; runtime owns tasks; outbound adapter owns subprocess/files;
  Spark entrypoint owns Iceberg procedure calls.
- Preconditions/rules: existing Iceberg table and location, Parquet for compaction, 3–168-hour
  retention/orphan rate, table-contained orphan location, configured concurrency and timeouts.
- Failures: InvalidInput, EntityNotFound, AlreadyExists, per-item batch errors, deterministic
  process timeout/failure, and four-failure compaction suspension. IAM/authorization is absent.
- Observability: before/after/stale/failure events at claims, transitions, scheduler, process, and
  result decoding, with repair hints and no raw configuration or credentials.
- Evidence: `glue/src/mystack/glue/application/table_optimizer.py`,
  `glue/src/mystack/glue/application/table_optimizer_runtime.py`,
  `glue/src/mystack/glue/adapters/outbound/table_optimizer_executor.py`,
  `glue/tests/test_table_optimizer_runtime.py`, `tests/e2e/test_glue_spark_catalog.py`, and
  `docs/protocols/glue/glue-table-optimizers.md`.
- Confidence: High for the documented Glue 5/Spark 3.5.4/Iceberg 1.7.1 path.

<!-- section: uc-016 -->
## UC-016: Generate test-declared compatibility evidence

- Purpose/actor/trigger: a contributor runs the compatibility evidence check or generation command
  after adding typed compatibility annotations to a contract or E2E test.
- Input: collected pytest metadata, pinned workspace/runtime facts, registered EMR/Glue operations,
  and checked-in generated artifacts.
- Output: deterministic case evidence, bilingual annotated-evidence documents, and CI matrices; a
  check reports duplicate/invalid metadata, stale outputs, or evidence/registry mismatches.
- Stored/changed data: generation updates only reviewed compatibility evidence artifacts; collection
  executes no test body.
- Preconditions/rules: registered strict pytest marker, bounded collection timeout, no forbidden
  heavyweight client imports during collection, and public-Proxy-compatible verification boundary.
- Failures: malformed/duplicate case IDs, unknown operations, missing source/test metadata, timeout,
  or generated-file drift.
- Observability: structured collection/compile/parity events with case count and source digest.
- Evidence: `scripts/compatibility/compatibility_evidence.py`, `tests/support/compatibility_plugin.py`,
  `contracts/compatibility-scope-policy.yaml`, `tests/test_compatibility_evidence.py`.
- Confidence: High

<!-- section: candidate-documentation -->
## Candidate gap: User documentation and contributor evidence

- Scope: a Markdown-first navigation layer separates user actions from implementation inventory;
  a static documentation site remains deferred.
- User outcome: a user can start Compose, choose Glue or EMR, find configuration and operations,
  and read a supported/not-supported client path without implementation detail.
- Contributor outcome: a contributor can find API/endpoint inventory, runtime architecture,
  configuration keys, CI evidence, and protocol repair locations without overloading user pages.
- Evidence: #79, #81, #87; [Spark documentation index](https://spark.apache.org/docs/latest/),
  [Trino deployment documentation](https://trino.io/docs/current/installation/deployment.html).
- Confidence: Candidate; implementation is issue-tracked and not yet a static-site commitment.
