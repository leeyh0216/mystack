# Project baseline

[한국어](baseline.ko.md) | English

## Metadata

- Status: approved and continuously maintained
- Owner: leeyh0216
- Updated: 2026-08-08
- Repository: private `leeyh0216/mystack`

## Purpose

Mystack is a Docker-first, protocol-compatible EMR and Glue Data Catalog emulator. It uses a transparent, extensible Proxy in front of LocalStack and executes real Spark 3.5.x EMR steps locally.

Glue Job, JobRun, and Crawler APIs are excluded. Glue scope is Data Catalog, Glue/Hive types, Hive interoperability, and Iceberg.

## Implemented facts

- Python uv workspace with independently packaged `shared` and `proxy` modules
- Pinned botocore model contract manifest with service and operation fingerprints
- AWS JSON 1.1 request validation, dispatch, success, and modeled-error codec
- Configuration-only Proxy route registry and transparent LocalStack fallback
- Versioned YAML configuration with generic nested environment overrides
- Structured boundary logs with payload hash/length but no payload or authorization contents
- Thread and asyncio task diagnostic endpoints with optional Bearer token
- GitHub milestones, bilingual issues, Python CI, model-drift, Docker E2E, and GHCR workflows
- Twelve passing shared/Proxy tests at this revision

## Entry points and commands

- Proxy executable: `mystack-proxy`
- Configuration: `config/mystack.yaml`
- Workspace install: `uv sync --locked --all-packages`
- Unit and contract tests: `uv run pytest -m "not e2e" --timeout 60`
- CI: `.github/workflows/ci.yml`
- Scheduled model drift: `.github/workflows/model-drift.yml`
- Docker E2E: `.github/workflows/e2e.yml`

## Confirmed decisions

- Long-term EMR goal: broad public API compatibility.
- Glue goal: Data Catalog public APIs; Jobs, JobRuns, and Crawlers are not planned.
- Errors reproduce documented validation, exception codes, HTTP status, state behavior, and side effects, not AWS bugs.
- Lower modules cannot know higher modules; Domain is independent of API, storage, Spark, and Docker.
- Every document has Korean and English variants and cites direct official sources.
- Every side-effect boundary logs before, after, and error events without secrets.
- All test classes have explicit configurable timeouts and E2E tests use the public Proxy endpoint.

## Remaining major gaps

- EMR domain/control-plane state machines, bootstrap runner, S3 resolver, and Spark runner
- Glue Data Catalog persistence and semantic operation handlers
- Spark Hive/Iceberg catalog integration
- Docker Compose runtime, public endpoint boto3 E2E, and management UI
- Generated operation-by-operation compatibility matrix

## Official references

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Official botocore models](https://github.com/boto/botocore/tree/develop/botocore/data)
- [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
- [AWS SDK custom endpoints](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
