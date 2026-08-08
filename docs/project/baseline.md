<!-- doc-id: project-baseline -->
<!-- lang: en -->

[한국어](baseline.ko.md) | [English](baseline.md)

# Project baseline

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
- Glue: 22 operations covering database, table/version, and partition/batch behavior with
  deterministic modeled shape maxima, natural errors, stable batch item order, and rollback. Serialized
  candidate transactions persist/fsync/replace schema-2 JSON before visible publication, migrate
  schema 1, and keep rename/cascade/version checks atomic. A bounded POSIX lock and latest-state
  reload extend the same transaction across emulator processes; documented domain errors translate
  at the inbound adapter.
- Glue responsibilities: immutable lossless domain snapshots own name/revision/archive/partition
  invariants; focused command/query/version/batch/pagination/initialization handlers own application
  policy; repositories expose collection snapshots and candidate transactions only.
- Interoperability: Spark 3.5.4 + Java 17, Glue/Hive complex types and S3 Parquet, Apache Iceberg
  1.7.1 create/append/read, dynamic overwrite, COW/MOR row-level DML, partition/schema/sort/identifier
  evolution, time travel, branch/tag writes, metadata/snapshot/maintenance procedures,
  rename/catalog-drop/tracked-file purge, S3 orphan cleanup and concurrent `VersionId` commit
  retry, and AWS SDK for pandas 3.17.0 Parquet/Glue E2E.
- Operations: service-aware Console for EMR cluster/Step commands and Glue metadata exploration,
  resource/log views, route/thread/task diagnostics, and structured boundary logs without
  authorization or payload contents. Console mutations traverse the same public AWS endpoint as boto3.
- Delivery: Python 3.11/3.12 CI, nightly/manual Docker E2E, model/API drift gates, anonymously
  consumable public GHCR multi-platform publication, SBOM/provenance, OCI index validation, and
  Trivy policy.
- Test policy: the fast suite is entirely local and contains no real-AWS comparison. The separate
  Docker/browser/Spark/Hive/Iceberg/AWS SDK for pandas E2E lane is CI-owned. Both layers apply
  explicit configured timeouts.

<!-- section: entry-points -->
## Entry points and commands

- Executables: `mystack-proxy`, `mystack-emr`, and `mystack-glue`
- Configuration: `config/mystack.yaml`; release configuration: `config/registry-release.json`
- Setup: `./scripts/bootstrap.sh`, `direnv allow`, or the provided Dev Container
- Fast verification: `make architecture-check`, `make test`, `make contract`, `make registry-check`,
  `make pre-commit`
- Runtime verification: `make up`, `make e2e`, `make down`
- CI: `.github/workflows/ci.yml`, `e2e.yml`, `model-drift.yml`, `release.yml`, `container-publish.yml`
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

### Unconfirmed

- The first all-component GHCR publication was still running during this scan; workflow structure is
  implemented, but this baseline does not claim all three remote packages passed their first scan.

<!-- section: candidates -->
## Remaining candidate gaps

New emulator services extend Proxy through the configuration-driven route registry. Service-specific
behavior changes remain ordinary reviewed source changes inside the owning bounded context.

<!-- section: confirmations -->
## Sequential confirmation log

- 2026-08-08: the user superseded the earlier A/B/C design and requested complete removal of the
  in-process SPI while retaining Proxy route extensibility.

<!-- section: next-sequence -->
## Recommended next sequence

1. Strengthen the GHCR release pre-push gate and GHCR-first onboarding.
2. Keep protocol and client drift repair hints synchronized with the implemented compatibility
   manifest.
3. Add newly reviewed clients and runtimes as explicit non-cross-product cases.
