<!-- doc-id: getting-started -->
<!-- lang: en -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Getting started

<!-- toc:start -->
## Contents

- [Start Docker Compose](#start-docker-compose)
- [Connect an AWS client](#connect-an-aws-client)
- [Continue by workload](#continue-by-workload)
- [Official sources](#official-sources)
<!-- toc:end -->

Start the published Docker Compose stack, verify it, and point an AWS client at the local endpoint.

<!-- section: start -->
## Start Docker Compose

Install Docker Engine with Docker Compose, then choose a published version.

```bash
export MYSTACK_IMAGE_TAG=<published-version>
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

The host endpoint is `http://localhost:4566`. A container on the same Compose network uses
`http://proxy:8080`.

<!-- section: clients -->
## Connect an AWS client

Use local development credentials and the same endpoint for each AWS service client.

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_EC2_METADATA_DISABLED=true

aws --endpoint-url "$AWS_ENDPOINT_URL" glue get-databases
aws --endpoint-url "$AWS_ENDPOINT_URL" emr list-clusters
```

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

For an application in another Docker Compose project, use `http://host.docker.internal:4566` and
add Docker's `host-gateway` mapping on Linux when required.

<!-- section: next -->
## Continue by workload

- [Glue Data Catalog](glue.md): boto3, AWS SDK for pandas, Spark Hive, and Iceberg.
- [Amazon EMR](emr.md): clusters, bootstrap actions, Spark/PySpark Steps, and logs.
- [Configuration](configuration.md): ports, timeouts, paths, and mounted configuration.
- [Operations](operations.md): management UI, diagnostics, upgrades, and cleanup.

<!-- section: sources -->
## Official sources

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint configuration](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
