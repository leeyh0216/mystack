<!-- doc-id: readme -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Mystack

<!-- toc:start -->
## Contents

- [Start with Docker Compose](#start-with-docker-compose)
- [Use Mystack](#use-mystack)
- [Contributors](#contributors)
- [Official sources](#official-sources)
<!-- toc:end -->

Mystack runs a local Amazon EMR and AWS Glue Data Catalog environment with Docker Compose. It is
designed for application and data-pipeline development with AWS clients, Spark, and LocalStack S3.

<!-- section: start -->
## Start with Docker Compose

Choose a published image version, download the matching Compose file, and start the stack.

```bash
export MYSTACK_IMAGE_TAG=<published-version>
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

Open the [documentation hub](docs/index.md) for the next task.

<!-- section: use -->
## Use Mystack

| I want to… | Start here |
| --- | --- |
| Start Docker Compose and connect an AWS client | [Getting started](docs/getting-started.md) |
| Use the Glue Data Catalog with boto3, AWS SDK for pandas, Spark Hive, or Iceberg | [Glue guide](docs/glue.md) |
| Create an EMR cluster, run a bootstrap action, or submit a Spark Step | [EMR guide](docs/emr.md) |
| Change ports, timeouts, storage, or runtime settings | [Configuration](docs/configuration.md) |
| Check supported client paths | [Compatibility](docs/compatibility/client-matrix.md) |
| Use the EMR or Glue management UI and diagnostics | [Operations](docs/operations.md) |

<!-- section: contribute -->
## Contributors

Architecture, protocol references, development setup, testing, CI, and release operations are in the
[Contributors guide](docs/maintainers.md). Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing
the repository.

<!-- section: sources -->
## Official sources

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Docker Compose reference](https://docs.docker.com/reference/compose-file/)
