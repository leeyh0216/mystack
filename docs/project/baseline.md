<!-- doc-id: project-baseline -->
<!-- lang: en -->

[한국어](baseline.ko.md) | [English](baseline.md)

# Project baseline

<!-- toc:start -->
## Contents

- [Metadata](#metadata)
- [Purpose and runtime](#purpose-and-runtime)
- [Code-derived facts](#code-derived-facts)
- [Entry points and commands](#entry-points-and-commands)
- [Confirmed architecture decisions](#confirmed-architecture-decisions)
- [Consistency result](#consistency-result)
- [Remaining candidate gaps](#remaining-candidate-gaps)
- [Sequential confirmation log](#sequential-confirmation-log)
- [Recommended next sequence](#recommended-next-sequence)
<!-- toc:end -->

<!-- section: metadata -->
## Metadata

- Status: approved
- Owner: leeyh0216
- Updated: 2026-08-09
- Repository: public `leeyh0216/mystack`
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`

<!-- section: purpose -->
## Purpose and runtime

Mystack is a Docker-first, protocol-compatible EMR and Glue Data Catalog emulator. A transparent,
configuration-driven Proxy routes AWS SDK traffic to independent service containers or LocalStack.
EMR executes real Spark 3.5.4 work locally; Glue persists Catalog metadata and interoperates with
Spark, Hive, and Apache Iceberg.

Glue Job, JobRun, and Crawler APIs are excluded. Glue scope is Data Catalog and its observable AWS
JSON 1.1 behavior. The official [EMR API](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
and [Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html) define the upstream
contracts.

<!-- section: facts -->
## Code-derived facts

- Workspace modules: `shared`, `proxy`, `emr`, and `glue`, each independently packaged except the
  development root.
- Composition roots: `proxy/src/mystack/proxy/app.py`, `emr/src/mystack/emr/app.py`, and
  `glue/src/mystack/glue/app.py`.
- Dependency direction: Domain → Application ports/use cases → Adapters → composition root. The
  executable contract resolves relative imports, rejects outward/cross-service/sibling dependencies
  and cycles, and proves each prohibited direction with mutation tests.
- Protocol boundary: pinned botocore models, AWS JSON 1.1 input validation, modeled responses/errors,
  explicit operation dispatch, and model/API fingerprints.
- Inbound mapping: five EMR and five Glue operation-family modules compose through a shared registry
  that rejects duplicate, missing, or unclassified handlers and is bidirectionally checked against
  implemented compatibility coverage.
- Proxy boundary: YAML route registry detects target/signing/host evidence; unknown services fall back
  to LocalStack without service-specific branches. A typed runtime owns the shared HTTP client and
  exposes separate AWS-request and management-forwarding capabilities without application-state
  reach-through.
- EMR: 13 operations, cluster/step state machines, bootstrap materialization from LocalStack S3,
  Python/JAR Spark execution, cancellation, logs, and management read models.
- EMR responsibilities: focused cluster-command, Step-command, query, pagination, failure-policy,
  and queue-driver components sit behind minimal inbound Protocols. A typed Build/Start/Close runtime
  cancels and awaits scheduler tasks and child processes with a file-configured shutdown deadline,
  closes artifacts, and releases driver locks.
- Glue: 28 operations covering database, table/version, partition/batch, and table optimizers with
  deterministic modeled shape maxima, natural errors, stable batch item order, and rollback. The
  source-built SQLite DB-API runtime is capability-gated before catalog initialization. A normalized
  SQLite catalog uses bounded writer retries, WAL, transactional schema initialization, and atomic
  database/table rename, cascade, and VersionId checks; documented domain errors translate at the
  inbound adapter.
- Glue responsibilities: immutable lossless domain snapshots own name/revision/archive/partition
  invariants; focused command/query/version/batch/pagination/initialization handlers own application
  policy; a separate Open Table Format planner/orchestrator owns Iceberg v2 input validation,
  metadata-store coordination, compensation, and catalog CAS; repositories expose collection
  snapshots and candidate transactions only. This follows the official Glue
  [`OpenTableFormatInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html).
- Interoperability: Spark 3.5.4 + Java 17, Glue/Hive complex types and S3 Parquet, Apache Iceberg
  1.7.1 Open Table Format create/update, create/append/read, dynamic overwrite, COW/MOR row-level
  DML, partition/schema/sort/identifier
  evolution, time travel, branch/tag writes, metadata/snapshot/maintenance procedures,
  rename/catalog-drop/tracked-file purge, S3 orphan cleanup and concurrent `VersionId` commit
  retry, and AWS SDK for pandas 3.17.0 Parquet/Glue E2E.
- Operations: service-aware Console for EMR cluster/Step commands and Glue metadata exploration,
  resource/log views, route/thread/task diagnostics, and structured boundary logs without
  authorization or payload contents. Console mutations traverse the same public AWS endpoint as boto3.
- Delivery: one stable `VERSION` authority, `feature/*` → `develop` → `main`, Python 3.11 CI,
  nightly/manual Docker E2E, model/API drift gates, immutable develop snapshots and main releases,
  multi-platform GHCR image publication, SBOM/provenance, OCI index validation, and Trivy policy.
- Test policy: the fast suite is entirely local and contains no real-AWS comparison. The separate
  Docker/browser/Spark/Hive/Iceberg/AWS SDK for pandas E2E lane is CI-owned. Both layers apply
  explicit configured timeouts.
- CI reporting publishes concise job summaries plus downloadable escaped HTML/JUnit test reports.
  Compatibility CI matrices and evidence are collected from typed pytest annotations without
  executing test bodies; the legacy YAML/API baselines remain required parity guards pending #87.

<!-- section: entry-points -->
## Entry points and commands

- Executables: `mystack-proxy`, `mystack-emr`, and `mystack-glue`
- Configuration: `config/runtime/mystack.yaml`; release/version configuration:
  `config/release/registry-release.json`, `config/release/version-files.json`, and root `VERSION`
- Setup: `./scripts/development/bootstrap.sh`, `direnv allow`, or the provided Dev Container
- Fast verification: `make version-check`, `make architecture-check`, `make test`, `make contract`,
  `make registry-check`, `make pre-commit`
- Runtime verification: `make up`, `make e2e`, `make down`
- CI: `.github/workflows/ci.yml`, `e2e.yml`, `model-drift.yml`, `release.yml`,
  `container-publish.yml`, `prepare-version-pr.yml`
- Implemented use cases: [implementation-derived catalog](usecase-catalog.md)

<!-- section: decisions -->
## Confirmed architecture decisions

- Lower modules cannot know higher modules. Business abstractions do not enter the shared wire package.
- Existing AWS CLI/boto clients use the single public Proxy endpoint; service containers are internal.
- Errors reproduce documented validation, code, status, state, and side effects—not AWS bugs.
- All behavior documents have Korean/English pairs and cite direct official sources.
- Side-effect boundaries log before, after, and failure events without secrets.
- Tests have explicit configurable timeouts and implemented operations have public-Proxy boto3 E2E.
- Service-specific behavior stays within its bounded context; Mystack exposes no in-process user plugin API.

These rules follow AWS [hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).

<!-- section: consistency -->
## Consistency result

### Confirmed

- Architecture, support scope, protocol, console, E2E, and release documents match the current code.
- Complete upstream classification records EMR 65 and Glue 299 modeled operations without claiming
  unimplemented operations are compatible.

### Corrected drift

- The previous baseline and use-case catalog still listed implemented EMR, Glue, Spark/Iceberg,
  Docker E2E, UI, and compatibility generation as future gaps. This scan replaces those stale claims.
- The previous test count described an early shared/Proxy slice rather than the current workspace.
- The 2026-08-09 documentation/CI scan found 92 Markdown documents without a common top index,
  mixed user and contributor material, 115 configuration leaf paths with only top-level coverage,
  and raw rather than human-readable test diagnostics. The Markdown-first navigation (#75) and
  readable CI reports (#80) are now implemented; a static-site decision remains deferred.

### Unconfirmed

- The `v0.1.3` workflow pushed all three images, but the anonymous external pull verification failed
  because package visibility has not yet been changed. GitHub Release creation was skipped; #45
  records that external blocker.

<!-- section: candidates -->
## Remaining candidate gaps

New emulator services extend Proxy through the configuration-driven route registry. Service-specific
behavior changes remain ordinary reviewed source changes inside the owning bounded context.

<!-- section: confirmations -->
## Sequential confirmation log

- 2026-08-08: the user superseded the earlier A/B/C design and requested complete removal of the
  in-process SPI while retaining Proxy route extensibility.
- 2026-08-09: after reviewing Spark, Trino, and the repository documentation/CI structure, the user
  selected a Markdown-first user documentation rewrite. A static documentation site is deferred.

<!-- section: next-sequence -->
## Recommended next sequence

1. Continue expanding implemented Glue and EMR operations only with their documented semantic,
   pagination, conflict, and state-transition contracts.
2. Keep the generated API inventory and client workflow labs synchronized with each supported client
   and pinned dependency version.
3. Complete GHCR public visibility and re-run the blocked v0.1.3 release transaction (#45, #55).
