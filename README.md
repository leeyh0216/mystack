<!-- doc-id: readme -->
<!-- lang: en -->

[한국어](README.ko.md) | [English](README.md)

# Mystack

Mystack is a protocol-compatible local emulator for Amazon EMR and AWS Glue. It sits in front of LocalStack, routes EMR and Glue AWS JSON 1.1 requests to dedicated emulators, and forwards every other AWS service without changing the request body.

The project targets:

- AWS CLI and AWS SDK compatibility through the documented wire protocols
- Amazon EMR cluster, bootstrap action, and step lifecycle emulation
- real Spark 3.5.x execution in local mode with LocalStack S3 access
- Glue Data Catalog behavior, including documented validation and service exceptions
- Spark 3.5.4 interoperability with Glue Data Catalog, Hive-compatible types, and Iceberg 1.7.1
- tiered `stable`, `application`, and exact-version `unsafe` Glue extension SPIs
- Versioned multi-platform Docker images published privately to GHCR

Glue Jobs, JobRuns, and Crawlers are intentionally out of scope. Compatibility is delivered incrementally and tracked in [the support scope](docs/support-scope.md) and [compatibility matrix](docs/compatibility/api-coverage.md).

<!-- section: quick-start -->
## Quick start

Docker Engine with Compose is the only runtime prerequisite. AWS CLI is optional; boto3 and other
AWS SDKs use the same endpoint.

```bash
cp .env.example .env
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 300
aws --endpoint-url http://localhost:4566 glue get-databases
```

Open `http://localhost:4566/_mystack/console` for the route, thread-stack, and asyncio-task
console. New users should start with the [detailed usage guide](docs/getting-started.md), which covers
Docker Compose combinations, boto3, application containers, and the provided Dev Container.

`make up CONFIG=path/in/repository.yaml` embeds the selected file in locally built
images; `compose.mount-config.yaml` optionally mounts a file read-only for live development or
prebuilt images. Use `MYSTACK__SECTION__KEY` only for deployment-specific overrides. See the
[configuration guide](docs/configuration.md) and [Docker Compose specification](https://docs.docker.com/reference/compose-file/).

<!-- section: architecture -->
## Architecture

Each service follows ports and adapters. Domain code has no dependency on FastAPI, boto3, Docker, subprocesses, or persistence implementations.

```text
AWS CLI / SDK
      |
      v
  proxy/  --------------------------> LocalStack (S3, ECR, other services)
    |  |
    |  +----------------------------> glue/
    +-------------------------------> emr/

domain <- application <- inbound/outbound adapters <- composition root
```

See [architecture.md](docs/architecture.md), [AWS protocol analysis](docs/protocols/aws-json-1.1.md), and [evolution policy](docs/evolution.md) for the detailed contracts. The architecture follows [AWS Prescriptive Guidance for hexagonal architectures](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).
User extension packaging, contexts, configuration, and Docker mounts are documented in the
[Glue extension SPI guide](docs/extensions.md).

<!-- section: status -->
## Status

The repository is under active construction. EMR currently exposes 13 boto3-tested operations,
and Glue exposes 22 boto3-tested Data Catalog operations. The baseline and
implementation-derived UseCase catalog live under [`docs/project`](docs/project).

Official behavior sources include the [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data), and [AWS Glue type-system documentation](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
