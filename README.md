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
- Spark 3.5.4 interoperability with Glue Data Catalog, Hive-compatible types, Iceberg 1.7.1, and
  documented [Open Table Format create/update inputs](docs/protocols/glue-open-table-format.md)
- Glue managed Iceberg compaction, snapshot-retention, and orphan-file optimizers through six
  boto3 APIs and bounded Glue 5 Spark workers
- AWS SDK for pandas 3.17.0 partitioned-Parquet and Glue Catalog round trips
- A reproducible local runtime based on Docker Compose

Glue Jobs, JobRuns, and Crawlers are intentionally out of scope. A passing E2E path is never a claim
that an entire library is supported. Consult the generated [release acceptance](docs/compatibility/release-acceptance.generated.md),
the [support scope](docs/support-scope.md), [client compatibility matrix](docs/compatibility/client-matrix.md),
and [API coverage](docs/compatibility/api-coverage.md) for exact boundaries.

<!-- section: quick-start -->
## Quick start

The normal path anonymously pulls the public published images; it does not clone or build this
repository. Install Docker Engine with Compose and download the Compose file from the same public
Git tag as the images. Choose an existing semantic tag from the package/release page. Public GHCR
packages require no registry token or registry login, as documented in GitHub's
[package permissions guide](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages).

```bash
export MYSTACK_IMAGE_TAG=v0.1.1  # replace with a published tag
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

Open the service-owned [EMR UI](http://localhost:4566/_mystack/ui/emr/) to create and operate
clusters, submit and track Steps, and follow/pause/download live logs. Open the service-owned
[Glue UI](http://localhost:4566/_mystack/ui/glue/) to explore databases, tables, schemas,
partitions, thread stacks, and asyncio tasks. Start with the [detailed usage guide](docs/getting-started.md) for Docker Compose combinations,
boto3, AWS SDK for pandas, upgrades, rollback, troubleshooting, and cleanup. Source builds belong in
the [development guide](docs/development.md), not the normal user path.

<!-- section: user-paths -->
## Find your task

| Task | Read |
| --- | --- |
| Start with Docker Compose | [Detailed usage guide](docs/getting-started.md) |
| Connect AWS CLI, boto3, or AWS SDK for pandas | [Client setup in the usage guide](docs/getting-started.md) |
| Check supported EMR/Glue APIs and errors | [Support scope](docs/support-scope.md), [API coverage](docs/compatibility/api-coverage.md) |
| Check release-blocking Glue/Hive/Iceberg/EMR guarantees | [Generated release acceptance](docs/compatibility/release-acceptance.generated.md) |
| Check Spark Glue Hive/Iceberg, Open Table Format, and library evidence | [Client compatibility matrix](docs/compatibility/client-matrix.md), [Open Table Format protocol](docs/protocols/glue-open-table-format.md) |
| Configure or call managed Iceberg table optimizers | [Table optimizer protocol](docs/protocols/glue-table-optimizers.md) |
| Change YAML, timeouts, ports, or Docker settings | [Configuration guide](docs/configuration.md) |
| Install an enterprise CA or proxy before EMR starts | [EMR pre-start guide](docs/protocols/emr-prestart.md) |
| Operate EMR, explore Glue, or inspect diagnostics | [Management console guide](docs/console.md) |

The [user guide](docs/index.md) provides the full recommended reading path.

<!-- section: support -->
## Current support level

The repository is under active construction. EMR currently exposes 13 boto3-tested operations,
and Glue exposes 28 boto3-tested Data Catalog operations. Spark 3.5.4 Hive/Iceberg and AWS SDK for
pandas 3.17.0 are supported only along the documented E2E paths. Athena, Glue Jobs/JobRuns/Crawlers,
production IAM, and YARN/HDFS environments are not currently supported.

<!-- section: maintainers -->
## Implementing or maintaining Mystack

Architecture, protocol, development, testing, CI, release, and upstream-evolution material is
separated into the [maintainer guide](docs/maintainers.md). Start there and follow the
[contributing guide](CONTRIBUTING.md) before changing the repository. Release maintainers use the
[version and branch workflow](docs/versioning.md); consumers continue to use immutable GHCR tags.

Official behavior sources include the [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data), and [AWS Glue type-system documentation](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
