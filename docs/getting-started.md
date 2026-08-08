<!-- doc-id: getting-started -->
<!-- lang: en -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Using Mystack

This guide takes a new user from startup through AWS CLI, boto3, AWS SDK for pandas, and Docker
Compose application integration. See the [support scope](support-scope.md) for implemented APIs and
explicit exclusions.

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

Install Docker Engine with Compose and authenticate GitHub CLI for access to the private repository.
No source clone, Python environment, Java installation, or local image build is needed. Pick a tag
that exists for all three `mystack-*` packages; `latest` is intentionally unavailable.

```bash
export MYSTACK_IMAGE_TAG=v0.1.0  # replace with a published tag
mkdir mystack-runtime && cd mystack-runtime
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.ghcr.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.ghcr.yaml
printf 'MYSTACK_IMAGE_TAG=%s\n' "$MYSTACK_IMAGE_TAG" > .env

export CR_PAT=YOUR_CLASSIC_PAT_WITH_READ_PACKAGES
echo "$CR_PAT" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
unset CR_PAT

docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

GitHub's [Container registry guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
requires a classic PAT with `read:packages` for a private local pull. `gh auth` separately authorizes
the one-file download from the private repository. Never save either token in `.env`.

The image-only Compose file contains no `build` key. It requires an explicit tag through Compose's
[required interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
and uses the configuration packaged in that release. Wait until all four containers are `healthy`.

```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 glue get-databases
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 emr list-clusters
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 s3 ls
```

These are local-emulator credentials, not AWS credentials. Never put real AWS credentials in this
runtime directory.

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
| Published image startup with packaged defaults | `-f compose.ghcr.yaml` |
| Mount a reviewed YAML configuration read-only | add `-f compose.mount-config.yaml` |
| Build or change Mystack source | use the [development guide](development.md), not this user path |

Download the configuration and overlay from the same Git tag before customizing them:

```bash
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/config/mystack.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > mystack.yaml
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.mount-config.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.mount-config.yaml
export MYSTACK_CONFIG_FILE="$PWD/mystack.yaml"
docker compose \
  -f compose.ghcr.yaml \
  -f compose.mount-config.yaml \
  up --detach --wait --wait-timeout 300
```

Compose merges later files into the earlier configuration. See the [Compose file merge
documentation](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) for exact rules
and the [configuration guide](configuration.md) for every YAML key and override precedence.

<!-- section: lifecycle -->
## Upgrade, rollback, and cleanup

Upgrade only to a tag that exists on Proxy, EMR, and Glue. Replace the Compose file from the same Git
tag, update `.env`, pull first, and let Compose recreate changed containers while preserving named
volumes:

```bash
export MYSTACK_IMAGE_TAG=v0.2.0
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.ghcr.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.ghcr.yaml
printf 'MYSTACK_IMAGE_TAG=%s\n' "$MYSTACK_IMAGE_TAG" > .env
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
```

Rollback uses the same sequence with the previous verified tag. For deployment-grade identity,
override `MYSTACK_PROXY_IMAGE`, `MYSTACK_EMR_IMAGE`, and `MYSTACK_GLUE_IMAGE` with the three full
`ghcr.io/...@sha256:...` values from release artifacts; these take precedence over the shared tag.
Keep the required `MYSTACK_IMAGE_TAG` entry in `.env` so Compose can validate every fallback.

```bash
docker compose -f compose.ghcr.yaml stop                  # preserve containers and data
docker compose -f compose.ghcr.yaml down                  # remove containers, preserve named volumes
docker compose -f compose.ghcr.yaml down --volumes        # permanently remove emulator state
```

The final command deletes EMR, Glue, and LocalStack data. On a shared machine, `docker logout ghcr.io`
also removes the saved GHCR login and can affect other private package pulls.

<!-- section: verify -->
## Verify and troubleshoot

```bash
docker compose -f compose.ghcr.yaml ps
docker compose -f compose.ghcr.yaml logs --tail 200 proxy glue emr
curl --fail http://localhost:4566/_mystack/routes
curl --fail http://localhost:4566/_mystack/diagnostics/threads
curl --fail http://localhost:4566/_mystack/diagnostics/tasks
open http://localhost:4566/_mystack/console
```

- `unauthorized` or `denied`: confirm package access, use a classic PAT with `read:packages`, then
  repeat `docker login ghcr.io`.
- `manifest unknown`: the selected tag must exist on all three packages; there is no `latest` tag.
- `connection refused`: inspect Proxy and dependency health with `docker compose ps`.
- Bind-mount permission error: inspect Docker Desktop file-sharing permission and absolute paths.
- Hung operation: inspect thread/task endpoints and component logs before changing configured
  service deadlines.
- Suspected protocol or client mismatch: compare the selected version with the generated [client
  compatibility evidence](compatibility/client-matrix.generated.md).

See the [observability guide](observability.md) for management endpoints and structured logs.

<!-- section: sources -->
## Official sources

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Compose file merge](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
