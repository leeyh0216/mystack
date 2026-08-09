<!-- doc-id: maintainer-guide -->
<!-- lang: en -->

[한국어](maintainers.ko.md) | [English](maintainers.md)

# Contributors

<!-- toc:start -->
## Contents

- [Start contributing](#start-contributing)
- [Architecture and dependencies](#architecture-and-dependencies)
- [Protocol and compatibility](#protocol-and-compatibility)
- [Implementation boundaries](#implementation-boundaries)
- [Tests and CI](#tests-and-ci)
- [Observability and release](#observability-and-release)
- [Issue-sized workflow](#issue-sized-workflow)
- [Official sources](#official-sources)
<!-- toc:end -->

This map is for contributors implementing, reviewing, operating, or releasing Mystack. If you use
Mystack from an application, start with the [user guide](index.md).

<!-- section: start -->
## Start contributing

1. Read the [contributing guide](../CONTRIBUTING.md) for branch, issue, commit, and review rules.
2. Set up `direnv`, uv, or the Dev Container with the [development guide](development.md).
3. Establish current state from the [project baseline](project/baseline.md) and
   [implementation-derived UseCases](project/usecase-catalog.md).
4. Run `make test`, `make contract`, and the required Docker E2E with explicit timeouts.

<!-- section: architecture -->
## Architecture and dependencies

- Components and dependency direction: [architecture](architecture.md)
- Keeping lower modules unaware of upper modules: [ADR-0001](adr/0001-hexagonal-service-boundaries.md)
- Versioned upstream adapters: [ADR-0002](adr/0002-versioned-upstream-adapters.md)
- Shared PEP 420 import namespace: [ADR-0003](adr/0003-pep420-namespace-packages.md)
- Registering another service in Proxy: [Proxy extension guide](extending-proxy.md)

<!-- section: protocol -->
## Protocol and compatibility

- AWS JSON 1.1 requests, responses, errors, and the Iceberg responsibility boundary:
  [protocol analysis](protocols/aws-json/aws-json-1.1.md)
- Deterministic partition validation, update, batch ordering, and partial success:
  [Glue partition/batch error contract](protocols/glue/glue-partition-batch-errors.md)
- Iceberg `VersionId` pointer CAS, process locking, retry evidence, and repair locations:
  [Iceberg GlueCatalog commit contract](protocols/glue/glue-iceberg-commits.md)
- Iceberg partition/schema/sort/identifier guarantees and client-drift repair locations:
  [Iceberg evolution contract](protocols/glue/glue-iceberg-evolution.md)
- Iceberg COW/MOR row-level writes, failed-commit evidence, and repair locations:
  [Iceberg row-level DML contract](protocols/glue/glue-iceberg-row-level-dml.md)
- Iceberg time travel, refs, metadata/maintenance procedures, S3 effects, and repair locations:
  [Iceberg snapshot/reference/procedure contract](protocols/glue/glue-iceberg-snapshots-refs-procedures.md)
- Iceberg rename/drop/purge ordering, compensation, and cross-system failure limits:
  [Iceberg lifecycle contract](protocols/glue/glue-iceberg-lifecycle.md)
- AWS Open Table Format request shapes, service-owned Iceberg metadata, S3 compensation, and repair
  locations: [Open Table Format input contract](protocols/glue/glue-open-table-format.md)
- Glue managed optimizer APIs, lifecycle, scheduler, Spark execution, and repair locations:
  [table optimizer contract](protocols/glue/glue-table-optimizers.md)
- Pinned botocore models and implementation status: [API coverage](compatibility/api-coverage.md)
- E2E claims by external client: [client compatibility matrix](compatibility/client-matrix.md)
- AWS, boto, and Spark evolution plus automated repair locations: [evolution policy](evolution.md)

When changing protocol behavior, update the model manifest, dispatcher, domain-error mapping,
public-Proxy contract, and E2E in the same issue rather than changing only a controller.

<!-- section: implementation -->
## Implementation boundaries

- File-first configuration schema and Docker overrides: [configuration guide](configuration.md)
- Composition roots and side-effect boundaries follow the dependency and logging rules in
  [architecture](architecture.md).
- Apply the [Korean technical-writing standard](korean-writing-style.md) when changing Korean and
  English documents together.

<!-- section: quality -->
## Tests and CI

- Unit, architecture, deterministic contract, and Docker E2E: [testing strategy](testing.md)
- Pull-request and scheduled workflows: [CI guide](ci.md)
- Every test command uses a timeout from `config/runtime/mystack.yaml` or an explicit `--timeout`.
- Protocol or client compatibility changes include both unit/contract coverage and real public-Proxy
  E2E evidence.

<!-- section: operations -->
## Observability and release

- Boundary logs, secret redaction, and thread/task stacks: [observability guide](observability.md)
- Resource/log UI and management API: [console guide](console.md)
- Version authority, branch policy, release retries, and recovery: [versioning guide](versioning.md)
- Public GHCR multi-platform builds, visibility, tags, SBOM, provenance, and scans: [container release](container-release.md)

<!-- section: workflow -->
## Issue-sized workflow

1. Before implementation, create a bilingual GitHub issue with milestone and area/type labels.
2. Complete code, tests, and user/maintainer documentation for that one issue together.
3. After local gates and required E2E pass, create one logical commit that references the issue.
4. Push immediately, inspect CI, and close the issue.
5. Split the next concern into a new issue and commit instead of accumulating completed work in the
   working tree.

<!-- section: sources -->
## Official sources

- [AWS guidance for adapting hexagonal architectures](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)
- [GitHub issue and pull-request linking](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [Docker Compose CI/CD](https://docs.docker.com/compose/how-tos/ci-cd/)
