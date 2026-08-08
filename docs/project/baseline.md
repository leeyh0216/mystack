<!-- doc-id: project-baseline -->
<!-- lang: en -->

[한국어](baseline.ko.md) | [English](baseline.md)

# Project baseline

<!-- section: metadata -->
## Metadata

- Status: approved
- Owner: leeyh0216
- Updated: 2026-08-08
- Repository: private `leeyh0216/mystack`
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
- Composition roots: `proxy/src/mystack_proxy/app.py`, `emr/src/mystack_emr/app.py`, and
  `glue/src/mystack_glue/app.py`.
- Dependency direction: Domain → Application ports/use cases → Adapters → composition root. Automated
  architecture tests reject inward imports of outer modules.
- Protocol boundary: pinned botocore models, AWS JSON 1.1 input validation, modeled responses/errors,
  explicit operation dispatch, and model/API fingerprints.
- Proxy boundary: YAML route registry detects target/signing/host evidence; unknown services fall back
  to LocalStack without service-specific branches.
- EMR: 13 operations, cluster/step state machines, bootstrap materialization from LocalStack S3,
  Python/JAR Spark execution, cancellation, logs, and management read models.
- Glue: 22 operations covering database, table/version, and partition/batch behavior; JSON persistence
  uses atomic replacement; documented domain errors translate at the inbound adapter.
- Glue extensions expose separate `stable`, `application`, and `unsafe` SPIs. A priority-ordered chain
  composes validated operation calls and revalidates final success output against botocore output shapes.
- Startup installs mounted wheels without network or dependency resolution and discovers providers by
  Python entry points. `unsafe` requires explicit permission and the exact installed Mystack version.
- Interoperability: Spark 3.5.4 + Java 17, Glue/Hive complex types and S3 Parquet, and Apache Iceberg
  1.7.1 create/append/read/schema-evolution E2E.
- Operations: resource/log console, route/thread/task diagnostics, structured boundary logs without
  authorization or payload contents.
- Delivery: Python 3.11/3.12 CI, nightly/manual Docker E2E, model/API drift gates, private GHCR
  multi-platform publication workflow, SBOM/provenance, OCI index validation, and Trivy policy.
- Extension Docker E2E verifies a real wheel install, identical Catalog access through all three SPI
  contexts, priority composition, and boto3 `AlreadyExistsException` behavior.
- Final test inventory: 63 collected. The fast suite passes 56 with two real-AWS opt-in skips; default
  Docker/browser/Spark/Hive/Iceberg E2E passes four with one extension-only skip; the separate
  extension Docker E2E passes its one test.

<!-- section: entry-points -->
## Entry points and commands

- Executables: `mystack-proxy`, `mystack-emr`, `mystack-glue`, and
  `mystack-glue-extension-bootstrap`
- Configuration: `config/mystack.yaml`; release configuration: `config/registry-release.json`
- Setup: `./scripts/bootstrap.sh`, `direnv allow`, or the provided Dev Container
- Fast verification: `make test`, `make contract`, `make registry-check`, `make pre-commit`
- Runtime verification: `make up`, `make e2e`, `make down`
- CI: `.github/workflows/ci.yml`, `e2e.yml`, `model-drift.yml`, `container-publish.yml`
- Implemented use cases: [implementation-derived catalog](usecase-catalog.md)

<!-- section: decisions -->
## Confirmed architecture decisions

- Lower modules cannot know higher modules. Business abstractions do not enter the shared wire package.
- Existing AWS CLI/boto clients use the single public Proxy endpoint; service containers are internal.
- Errors reproduce documented validation, code, status, state, and side effects—not AWS bugs.
- All behavior documents have Korean/English pairs and cite direct official sources.
- Side-effect boundaries log before, after, and failure events without secrets.
- Tests have explicit configurable timeouts and implemented operations have public-Proxy boto3 E2E.
- Extension authors select one of three Glue SPIs by access and compatibility level. Domain and
  application layers never import extension packages; only the composition root constructs contexts.

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

Extensions currently execute trusted code in the Glue process. Separate-process or remote-sidecar
isolation is not implemented. The common operation chain is reusable by other emulators, but a public
EMR SPI and context require a separate product decision.

<!-- section: confirmations -->
## Sequential confirmation log

- 2026-08-08: the user confirmed all A/B/C access levels as separate SPIs.
- A became snapshot/capability-oriented `stable`, B direct application access, and C exact-version
  `unsafe`.

<!-- section: next-sequence -->
## Recommended next sequence

1. Implement a real team correction through `stable` and collect missing capabilities.
2. Evaluate a separately packaged SPI v1 compatibility test kit.
3. After operating the common chain, design public contexts for EMR and other services independently.
