# Development setup

[한국어](development.ko.md) | English

## Prerequisites

- Git and GitHub CLI authenticated for the private repository
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker Desktop or Docker Engine with Compose](https://docs.docker.com/compose/install/)
- Optional [direnv](https://direnv.net/) for automatic local environment loading
- At least 12 GB free disk space for Spark/Glue-compatible images and test data

## Ten-minute setup

```bash
gh repo clone leeyh0216/mystack
cd mystack
cp .env.example .env
direnv allow                 # optional
make bootstrap
make up
```

Verify the public endpoint and effective routes:

```bash
curl http://localhost:4566/_mystack/health
make routes
AWS_ENDPOINT_URL=http://localhost:4566 aws s3 ls
```

The AWS endpoint environment follows the [official SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html).

## Configuration precedence

1. `config/mystack.yaml`
2. generic `MYSTACK__SECTION__KEY` environment override
3. executable `--config`, `--host`, and `--port` options where supported

Examples:

```bash
export MYSTACK_CONFIG_FILE=config/mystack.yaml
export MYSTACK__LOGGING__LEVEL=DEBUG
export MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600
mystack-proxy --config "$MYSTACK_CONFIG_FILE"
```

In Docker the same file is mounted read-only, following [Docker Compose configs](https://docs.docker.com/reference/compose-file/configs/). Never commit shared-environment management tokens or real AWS credentials.

## Daily commands

Run `make help` for the source of truth. Common flows:

```bash
make format
make test
make contract
make e2e
make logs SERVICE=emr
make threads
make down
```

Timeouts come from the YAML `tests` section. Service process/bootstrap timeouts are separate so a hung subprocess is stopped by its adapter before the outer test timeout whenever possible.

## Where to make changes

- Wire metadata or generic JSON serialization: `shared/src/mystack_aws_protocol`
- Proxy route behavior: `proxy/src/mystack_proxy`; add services through YAML first
- EMR state/behavior: `emr/src/mystack_emr/domain` and `application`
- Glue Catalog behavior: `glue/src/mystack_glue/domain` and `application`
- S3, process, database, FastAPI: service `adapters`
- Dependency wiring only: service composition root

The dependency direction is enforced using the [AWS hexagonal architecture model](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).

## Troubleshooting

- `make bootstrap` reports missing tools, broken docs, model drift, or fast-test failures.
- `make logs SERVICE=proxy` shows JSON boundary events.
- `make threads` and `make tasks` capture live stacks without frame locals.
- `model-drift-report.json` names changed operations and fix locations.
- E2E failure artifacts include all container logs.

