<!-- doc-id: getting-started -->
<!-- lang: en -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Using Mystack

This guide takes a new user from startup through AWS CLI, boto3, Docker Compose application, and Dev
Container integration. See the [support scope](support-scope.md) for implemented APIs and the [Glue
extension SPI guide](extensions.md) for behavior customization.

<!-- section: choose -->
## Choose an environment

| Environment | Best for | AWS endpoint |
| --- | --- | --- |
| Docker Compose on the host | Application developers consuming Mystack | `http://localhost:4566` |
| Provided Dev Container | Mystack code and extension developers | `http://host.docker.internal:4566` |
| Container on the same Compose network | A service running beside Mystack | `http://proxy:8080` |

Proxy is Mystack's single public endpoint. It routes by `X-Amz-Target`, SigV4 signing service, and
host evidence to EMR, Glue, or LocalStack. SDK configuration follows the official [AWS SDK endpoint
configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html).

<!-- section: compose -->
## Start with Docker Compose

Install Docker Engine with Compose, then clone the private repository. Allow at least 12 GB of free
space for the first Spark and Glue image build.

```bash
gh repo clone leeyh0216/mystack
cd mystack
cp .env.example .env
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

The Compose file and `--wait` behavior follow the [Docker Compose
documentation](https://docs.docker.com/reference/cli/docker/compose/up/). Wait until every container
is `healthy` before starting clients.

```bash
aws --endpoint-url http://localhost:4566 glue get-databases
aws --endpoint-url http://localhost:4566 emr list-clusters
aws --endpoint-url http://localhost:4566 s3 ls
```

The credentials in `.env.example` are local-emulator values. Never place real AWS credentials in
`.env` or the repository. Use `docker compose stop` when you want to preserve data. `make down`
removes the test volumes and therefore deletes their stored data.

<!-- section: clients -->
## Connect boto3 and applications

Point each boto3 client at the same endpoint:

```python
import boto3

glue = boto3.client(
    "glue",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
print(glue.get_databases())
```

Pass these variables to an application running on the host:

```dotenv
AWS_ENDPOINT_URL=http://localhost:4566
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_EC2_METADATA_DISABLED=true
```

When Mystack and the application share a Compose network, set
`AWS_ENDPOINT_URL=http://proxy:8080`. A separate Docker Desktop container can use
`http://host.docker.internal:4566`. On Linux, add this host mapping to the application service:

```yaml
services:
  my-application:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      AWS_ENDPOINT_URL: http://host.docker.internal:4566
```

This mapping uses Docker's special [host-gateway
value](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host).

<!-- section: overlays -->
## Compose overlays and configuration

| Purpose | File to add to the command |
| --- | --- |
| Default local build and startup | `-f compose.yaml` |
| Mount YAML configuration without rebuilding | `-f compose.mount-config.yaml` |
| Mount Glue extension wheels read-only | `-f compose.extensions.yaml` |
| Isolated repository E2E for all three SPIs | `make extension-e2e` |

For example, apply both a configuration file and Glue extension directory:

```bash
export MYSTACK_CONFIG_FILE="$PWD/config/mystack.yaml"
export MYSTACK_GLUE_EXTENSIONS_DIR="$PWD/extensions"
docker compose \
  -f compose.yaml \
  -f compose.mount-config.yaml \
  -f compose.extensions.yaml \
  up --build --detach --wait
```

Compose merges later files into the earlier configuration. See the [Compose file merge
documentation](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) for exact rules
and the [configuration guide](configuration.md) for every YAML key and override precedence.

<!-- section: devcontainer -->
## Develop in the Dev Container

The repository includes `.devcontainer/devcontainer.json`. Install Docker and the VS Code Dev
Containers extension on the host, open a local clone, and run `Dev Containers: Reopen in Container`
from the Command Palette. This is the workflow in the official [Dev Container creation
guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container).

The Dev Container provides:

- Python 3.11 and digest-pinned uv 0.11.8
- Docker CLI and Compose using the host Docker daemon
- AWS CLI and GitHub CLI
- locked workspace dependencies and the pre-commit hook
- Python, Ruff, TOML, and YAML editor extensions

The repository commits both feature versions in `devcontainer.json` and resolved digests in
`devcontainer-lock.json`. CI builds the actual image with the [official Dev Container
CLI](https://github.com/devcontainers/cli) and `--frozen-lockfile`, so contributors receive the same
tool set.

After `postCreateCommand` finishes, run these commands in its terminal:

```bash
make test
make up
curl --fail "$AWS_ENDPOINT_URL/_mystack/health"
aws --endpoint-url "$AWS_ENDPOINT_URL" glue get-databases
make extension-e2e
```

The environment uses the [Docker-outside-of-Docker
feature](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker). It mounts
the workspace at the same absolute path on the host and in the container, allowing the host daemon to
resolve Compose configuration and extension bind mounts. Open a host-local clone with `Reopen in
Container`; do not use `Clone Repository in Container Volume`. Keep host and Dev Container
architectures equal on Apple Silicon.

<!-- section: verify -->
## Verify and troubleshoot

```bash
make routes
make logs SERVICE=glue
make threads
make tasks
open http://localhost:4566/_mystack/console
```

- `connection refused`: inspect Proxy and dependency health with `docker compose ps`.
- Bind-mount permission error: inspect Docker Desktop file-sharing permission and absolute paths.
- Missing extension: search logs for `extension.install.*` and `extension.provider.load.*`.
- Suspected protocol change: run `make model-check` and `make coverage-check`.
- Hung test: tune `tests.*_timeout_seconds` in `config/mystack.yaml` and inspect thread/task endpoints.

See the [observability guide](observability.md) for management endpoints and structured logs.

<!-- section: sources -->
## Official sources

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Compose file merge](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Dev Container creation guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container)
- [Docker-outside-of-Docker feature](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker)
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
