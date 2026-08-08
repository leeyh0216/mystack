<!-- doc-id: getting-started -->
<!-- lang: en -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Using Mystack

This guide takes a new user from startup through AWS CLI, boto3, AWS SDK for pandas, and Docker
Compose application integration. See the [support scope](support-scope.md) for implemented APIs and the [Glue
extension SPI guide](extensions.md) for behavior customization.

<!-- section: choose -->
## Choose an environment

| Environment | Best for | AWS endpoint |
| --- | --- | --- |
| Docker Compose on the host | Application developers consuming Mystack | `http://localhost:4566` |
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

AWS SDK for pandas (`awswrangler`) needs the per-service Glue and S3 endpoints to point at the same
Proxy. This example creates a bucket and database, registers partitioned Parquet data and a Glue
table, and reads the dataset back:

```bash
export AWS_ENDPOINT_URL_GLUE=http://localhost:4566
export AWS_ENDPOINT_URL_S3=http://localhost:4566
```

```python
import awswrangler as wr
import boto3
import pandas as pd

boto3.client("s3").create_bucket(Bucket="mystack-example")
wr.catalog.create_database(name="demo")
wr.s3.to_parquet(
    df=pd.DataFrame({"id": [1, 2], "day": ["2026-08-08", "2026-08-09"]}),
    path="s3://mystack-example/events/",
    dataset=True,
    database="demo",
    table="events",
    partition_cols=["day"],
)
print(wr.s3.read_parquet(path="s3://mystack-example/events/", dataset=True))
```

See the [client compatibility matrix](compatibility/client-matrix.md) for the verified functions and
excluded services. In particular, `wr.athena.*` is currently out of scope.

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
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
