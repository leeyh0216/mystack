<!-- doc-id: project-usecase-catalog -->
<!-- lang: en -->

[한국어](usecase-catalog.ko.md) | [English](usecase-catalog.md)

# Implementation-derived UseCase catalog

<!-- section: metadata -->
## Metadata and scope

- Status: approved
- Updated: 2026-08-08
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`
- Included: HTTP endpoints, application operations, runtime processes, management UI, release CLI/workflow
- Excluded: remote extension sidecars, public EMR SPI, and Glue Jobs/JobRuns/Crawlers
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
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack_proxy/routing.py:32`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack_proxy/forwarder.py:57`
- Confidence: High

<!-- section: uc-002 -->
## UC-002: Execute an AWS JSON 1.1 operation

- Purpose/actor/trigger: EMR/Glue inbound endpoint processes an `X-Amz-Target` POST.
- Input: required target and JSON object; optional SigV4 metadata. Pinned operation input shape,
  required/type/enum/pattern constraints are validated before dispatch.
- Output: modeled JSON 200 response or AWS-compatible error body/status/headers.
- Side effects: runs matching middleware and invokes the built-in handler at most once.
- Preconditions/rules: recognized official operation; unsupported recognized operations return 501.
- Failures: unknown operation, serialization/validation error, domain error, protected internal error.
- Observability: service/operation/model fingerprint, input/output member names, request ID, duration.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack_aws_protocol/endpoint.py:49`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack_aws_protocol/dispatcher.py:38`
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
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/adapters/inbound/aws.py:40`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/application/service.py:65`
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
- Failures: missing artifact, bootstrap failure, process timeout/exit, cancellation, invalid application args.
- Observability: S3/process before/after/failure events; Python and JAR Spark S3A/cancel E2E.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/adapters/outbound/runtime.py:46`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/adapters/outbound/runtime.py:282`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/adapters/outbound/runtime.py:326`
- Confidence: High

<!-- section: uc-005 -->
## UC-005: Manage Glue databases

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeleteDatabase or import status.
- Input: CatalogId, name, DatabaseInput, pagination token/page size; official shape and normalized non-empty
  name rules.
- Output: modeled database documents/list/next token or empty response.
- Stored/changed data: JSON-backed database record; optional default database on initialization.
- Side effects: atomic state-file replacement after mutations.
- Preconditions/rules: case-normalized keys, uniqueness, child constraints, bounded pagination.
- Failures: AlreadyExists, EntityNotFound, InvalidInput and invalid pagination token.
- Observability: repository read/write and persistence boundary events; direct/public boto3 tests.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/application/service.py:60`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/adapters/outbound/repository.py:300`
- Confidence: High

<!-- section: uc-006 -->
## UC-006: Manage Glue tables and versions

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeleteTable or GetTableVersion(s).
- Input: CatalogId, database/name, TableInput, expression/attributes, VersionId, SkipArchive and pagination.
- Output: table/version documents, lists/next token, or empty modeled response.
- Stored/changed data: current table, monotonically incremented version and optional archive.
- Side effects: atomic persistence; no Iceberg metadata-format implementation in Mystack.
- Preconditions/rules: database exists, unique normalized name, optimistic version and archive behavior.
- Failures: AlreadyExists, EntityNotFound, VersionMismatch, InvalidInput; open-table-format input excluded.
- Observability: mapped domain errors and version/persistence tests; Spark Hive/Iceberg E2E consumes API.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/application/service.py:101`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/application/service.py:149`
- Confidence: High

<!-- section: uc-007 -->
## UC-007: Manage Glue partitions and batch results

- Purpose/actor/trigger: boto3/CLI calls Create/Get/List/Update/DeletePartition or four batch operations.
- Input: Catalog/database/table, partition values/input, expression, segment, pagination and schema flags.
- Output: partition/list/batch documents; batch errors are per-entry rather than whole-call failure.
- Stored/changed data: partition records keyed by catalog/database/table/value tuple.
- Side effects: atomic state persistence after mutation.
- Preconditions/rules: table exists; value count equals partition-key count; supported predicate/segment.
- Failures: AlreadyExists, EntityNotFound, InvalidInput and per-item ErrorDetail.
- Observability: operation/error logs and all 22 Glue operations through public Proxy E2E.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/application/service.py:213`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/adapters/inbound/aws.py:201`
- Confidence: High

<!-- section: uc-008 -->
## UC-008: Inspect service resources and EMR logs

- Purpose/actor/trigger: operator/UI calls versioned management endpoints through Proxy.
- Input: component/path, optional Bearer management token, resource/log query and configured page limit.
- Output: EMR cluster/step/log read models or Glue database/table/partition tree.
- Stored/changed data/events: none; management access audit event.
- Side effects: Proxy makes one internal management HTTP call; raw step arguments are not exposed.
- Preconditions/rules: known component, management enabled/token valid, application API pagination.
- Failures: unauthorized/disabled, unknown component/resource, internal service timeout.
- Observability: management forwarding and component adapter boundary logs plus UI E2E.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack_proxy/app.py:122`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack_emr/app.py:134`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/app.py:120`
- Confidence: High

<!-- section: uc-009 -->
## UC-009: Inspect thread/task stacks

- Purpose/actor/trigger: operator/UI calls `/_mystack/diagnostics/threads` or `/tasks`.
- Input: optional Bearer token and configured stack-frame limit.
- Output: thread/task metadata and source stack lines, never frame locals.
- Stored/changed data/events: no resource mutation; diagnostic access audit log.
- Preconditions/rules: diagnostics enabled and token valid if configured.
- Failures: disabled or unauthorized.
- Observability: access result/client without token contents.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack_aws_protocol/diagnostics.py:55`
- Confidence: High

<!-- section: uc-010 -->
## UC-010: Operate the browser management console

- Purpose/actor/trigger: local operator opens `/_mystack/console` and selects tabs/resources/logs.
- Input: component/tab/resource selection, refresh action and optional management token.
- Output: accessible status, compatibility, resource detail, logs, route and stack views.
- Stored/changed data/events: browser view state only; invokes read-only management endpoints.
- Preconditions/rules: packaged static asset and public Proxy; keyboard/ARIA tab contract.
- Failures: unavailable component/endpoint/token displays non-secret error state.
- Observability: Playwright keyboard/resource/log/browser E2E and captured screenshot.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack_proxy/console.py:12`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/tests/e2e/test_console_browser.py:21`
- Confidence: High

<!-- section: uc-011 -->
## UC-011: Publish and verify private multi-platform images

- Purpose/actor/trigger: maintainer pushes a semantic tag or manually dispatches GHCR publication.
- Input: component/version plus file-configured packages, Dockerfiles, platforms, Trivy version/policy and
  explicit timeouts.
- Output: private GHCR tags/digests, BuildKit SBOM/provenance, raw OCI index and scan/release artifacts.
- Stored/changed data: GHCR packages and GitHub workflow artifacts.
- Side effects: token login, image build/push/pull, scanner DB/image downloads.
- Preconditions/rules: ephemeral `GITHUB_TOKEN`, new tag, amd64+arm64 index; never `latest`.
- Failures: permission/tag collision, build/push, platform verification, timeout or vulnerability policy.
- Observability: registry before/after/failure events and uploaded evidence.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/.github/workflows/container-publish.yml:1`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/scripts/registry_release.py:75`
- Confidence: High for implementation; first complete remote three-package run not yet confirmed.

<!-- section: uc-012 -->
## UC-012: Compose a Glue operation extension

- Purpose/actor/trigger: an extension author wraps or replaces one Glue operation while retaining the
  built-in behavior when desired.
- Input: validated `OperationCall`, single-use `OperationNext`, tier-specific context, provider priority,
  and timeout.
- Output: mapping conforming to the official output shape or a documented `AwsServiceError`.
- Stored/changed data: accesses snapshots/capabilities, `CatalogApplication`, or repository/settings by SPI.
- Side effects: executes in-process middleware by priority and ID, optionally invoking the built-in handler.
- Preconditions/rules: `stable`, `application`, and `unsafe` use separate [Python entry-point
  groups](https://packaging.python.org/en/latest/specifications/entry-points/). `unsafe` requires explicit
  permission and the exact installed version.
- Failures: duplicate ID, unknown operation, missing entry point, version mismatch, timeout, repeated next
  call, or invalid output.
- Observability: provider-load and operation-invoke before/after/error events with API version, SPI,
  extension ID, duration, and repair hint.
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack_aws_protocol/dispatcher.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/extensions.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/tests/test_extensions.py`
- Confidence: High

<!-- section: uc-013 -->
## UC-013: Install and verify Glue extension wheels

- Purpose/actor/trigger: at Glue container startup, an operator supplies mounted wheel files.
- Input: YAML wheel/install directories, install timeout, provider list, and read-only volume.
- Output: target install and `.pth` file discoverable by the following process.
- Stored/changed data: dedicated temporary install directory and virtual-environment path file.
- Side effects: invokes `pip --no-index --no-deps` as a subprocess, then starts the application process.
- Preconditions/rules: extension code is trusted; every dependency wheel must be mounted explicitly.
- Failures: no wheels skips only when no providers require them; installation failure, timeout, or missing
  provider rejects startup safely.
- Observability: wheel names/count, install before/after/failure, and provider distribution/version; no pip
  output or credentials.
- Verification: places a real example wheel in an isolated named volume and checks boto3's documented
  [CreatePartition error](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html).
- Evidence: `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack_glue/extension_bootstrap.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/tests/e2e/test_glue_extensions.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/compose.extension-e2e.yaml`
- Confidence: High
