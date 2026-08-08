<!-- doc-id: readme -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Mystack

Mystack is a Docker application that emulates Amazon EMR and AWS Glue Data Catalog locally through
their official protocols. Consumers point AWS CLI, boto3, and existing clients at one endpoint,
`http://localhost:4566`. Proxy routes EMR and Glue requests to dedicated emulators and forwards other
AWS services to LocalStack without changing the request body.

The current primary paths are:

- AWS CLI and AWS SDK compatibility through the documented wire protocols
- Amazon EMR cluster, bootstrap action, and step lifecycle emulation
- real Spark 3.5.x execution in local mode with LocalStack S3 access
- live EMR Step stdout/stderr with pause/resume/download, restart recovery, and S3 log publication
- Glue Data Catalog behavior, including documented validation and service exceptions
- Spark 3.5.4 interoperability with Glue Data Catalog, Hive-compatible types, and Iceberg 1.7.1
- AWS SDK for pandas 3.17.0 partitioned-Parquet and Glue Catalog round trips
- A reproducible local runtime based on Docker Compose

Glue Jobs, JobRuns, and Crawlers are intentionally out of scope. A passing E2E path is never a claim
that an entire library is supported. Consult the [support scope](docs/support-scope.md), [client
compatibility matrix](docs/compatibility/client-matrix.md), and [API coverage](docs/compatibility/api-coverage.md)
for exact boundaries.

<!-- section: quick-start -->
## Quick start

The normal path anonymously pulls the public published images; it does not clone or build this
repository. Install Docker Engine with Compose and download the Compose file from the same public
Git tag as the images. Choose an existing semantic tag from the package/release page. Public GHCR
packages require no registry token or registry login, as documented in GitHub's
[package permissions guide](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages).

```bash
export MYSTACK_IMAGE_TAG=v0.1.0  # replace with a published tag
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

Open `http://localhost:4566/_mystack/console` to create and operate EMR clusters, submit and track
Steps, follow/pause/download live logs, explore Glue databases/tables/schemas/partitions, and view routes, thread
stacks, and asyncio tasks. Start with the [detailed usage guide](docs/getting-started.md) for Docker Compose combinations,
boto3, AWS SDK for pandas, upgrades, rollback, troubleshooting, and cleanup. Source builds belong in
the [development guide](docs/development.md), not the normal user path.

<!-- section: user-paths -->
## Find your task

| Task | Read |
| --- | --- |
| Start with Docker Compose | [Detailed usage guide](docs/getting-started.md) |
| Connect AWS CLI, boto3, or AWS SDK for pandas | [Client setup in the usage guide](docs/getting-started.md) |
| Check supported EMR/Glue APIs and errors | [Support scope](docs/support-scope.md), [API coverage](docs/compatibility/api-coverage.md) |
| Check Spark Glue Hive/Iceberg and library evidence | [Client compatibility matrix](docs/compatibility/client-matrix.md) |
| Change YAML, timeouts, ports, or Docker settings | [Configuration guide](docs/configuration.md) |
| Install an enterprise CA or proxy before EMR starts | [EMR pre-start guide](docs/protocols/emr-prestart.md) |
| Operate EMR, explore Glue, or inspect diagnostics | [Management console guide](docs/console.md) |

The [user guide](docs/index.md) provides the full recommended reading path.

<!-- section: support -->
## Current support level

The repository is under active construction. EMR currently exposes 13 boto3-tested operations,
and Glue exposes 22 boto3-tested Data Catalog operations. Spark 3.5.4 Hive/Iceberg and AWS SDK for
pandas 3.17.0 are supported only along the documented E2E paths. Athena, Glue Jobs/JobRuns/Crawlers,
production IAM, and YARN/HDFS environments are not currently supported.

<!-- section: maintainers -->
## Implementing or maintaining Mystack

Architecture, protocol, development, testing, CI, release, and upstream-evolution material is
separated into the [maintainer guide](docs/maintainers.md). Start there and follow the
[contributing guide](CONTRIBUTING.md) before changing the repository.

Official behavior sources include the [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data), and [AWS Glue type-system documentation](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
