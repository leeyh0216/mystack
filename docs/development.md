<!-- doc-id: development -->
<!-- lang: en -->

[한국어](development.ko.md) | [English](development.md)

# Development setup

<!-- section: prerequisites -->
## Prerequisites

- Git and GitHub CLI authenticated for the private repository
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker Desktop or Docker Engine with Compose](https://docs.docker.com/compose/install/)
- Optional [direnv](https://direnv.net/) for automatic local environment loading
- At least 12 GB free disk space for Spark/Glue-compatible images and test data

<!-- section: setup -->
## Ten-minute setup

```bash
gh repo clone leeyh0216/mystack
cd mystack
cp .env.example .env
direnv allow                 # optional
make bootstrap
make pre-commit
make up
```

Verify the public endpoint and effective routes:

```bash
curl http://localhost:4566/_mystack/health
make routes
AWS_ENDPOINT_URL=http://localhost:4566 aws s3 ls
```

The AWS endpoint environment follows the [official SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html).

<!-- section: devcontainer -->
## Dev Container setup

When Docker and the VS Code Dev Containers extension are available on the host, no separate Python,
uv, or AWS CLI installation is required. Open a local clone and run `Dev Containers: Reopen in
Container`. `.devcontainer/devcontainer.json` mounts the workspace at the same absolute host path and
uses the host Docker daemon. Run `make up` and `make test` after creation completes.

The container provides Python 3.11, digest-pinned uv, Docker CLI/Compose, AWS CLI, GitHub CLI, locked
workspace dependencies, pre-commit, and editor extensions. Commit feature versions in
`devcontainer.json` with resolved digests in `devcontainer-lock.json`. CI builds the same image with
the [official Dev Container CLI](https://github.com/devcontainers/cli) and `--frozen-lockfile`.

After `postCreateCommand` completes, verify the environment:

```bash
make test
make up
curl --fail "$AWS_ENDPOINT_URL/_mystack/health"
aws --endpoint-url "$AWS_ENDPOINT_URL" glue get-databases
```

The Dev Container uses the [Docker-outside-of-Docker
feature](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker). Reopen a
host-local clone; do not use `Clone Repository in Container Volume`. The host daemon resolves Compose
configuration bind mounts, so the workspace must have the same absolute path on the
host and in the container. Keep both architectures equal on Apple Silicon. This setup follows the
official [Dev Container creation
guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container).

<!-- section: precedence -->
## Configuration precedence

1. executable `--config`, `MYSTACK_CONFIG_FILE`, or the default selects a YAML file
2. generic `MYSTACK__SECTION__KEY` environment overrides its nested values
3. executable `--host` and `--port` override only the process listener

Examples:

```bash
export MYSTACK_CONFIG_FILE=config/mystack.yaml
export MYSTACK__LOGGING__LEVEL=DEBUG
export MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600
mystack-proxy --config "$MYSTACK_CONFIG_FILE"
```

`make up CONFIG=...` embeds a repository-local YAML file at build time. For a read-only live
mount, add `-f compose.mount-config.yaml` as described in the [configuration guide](configuration.md).
Both modes follow [Docker Compose configs](https://docs.docker.com/reference/compose-file/configs/).
Never commit shared-environment management tokens or real AWS credentials.

<!-- section: commands -->
## Daily commands

Run `make help` for the source of truth. Common flows:

```bash
make format
make pre-commit
make requirements
make coverage-check
make test
make contract
make e2e
make logs SERVICE=emr
make threads
make down
```

Timeouts come from the YAML `tests` section. Service process/bootstrap timeouts are separate so a hung subprocess is stopped by its adapter before the outer test timeout whenever possible.

`make pre-commit` installs and runs repository-local hooks backed by `uv.lock`. The hooks reject
lint/format, bilingual documentation, container requirement lock, and botocore model-manifest
drift. Their lifecycle follows the official [pre-commit installation and usage
contract](https://pre-commit.com/#install).

<!-- section: locations -->
## Where to make changes

- Wire metadata or generic JSON serialization: `shared/src/mystack_aws_protocol`
- Proxy route behavior: `proxy/src/mystack_proxy`; add services through YAML first
- EMR state/behavior: `emr/src/mystack_emr/domain` and `application`
- Glue Catalog behavior: `glue/src/mystack_glue/domain` and `application`
- S3, process, database, FastAPI: service `adapters`
- Dependency wiring only: service composition root

The dependency direction is enforced using the [AWS hexagonal architecture model](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).

<!-- section: troubleshooting -->
## Troubleshooting

- `make bootstrap` reports missing tools, broken docs, model drift, or fast-test failures.
- `make logs SERVICE=proxy` shows JSON boundary events.
- `make threads` and `make tasks` capture live stacks without frame locals.
- `model-drift-report.json` names changed operations and fix locations.
- `api-coverage-drift-report.json` names unclassified, removed, shape-changed, or
  misclassified operations and the owning boundary to update.
- E2E failure artifacts include all container logs.
