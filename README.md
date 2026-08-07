# Mystack

[한국어](README.ko.md) | English

Mystack is a protocol-compatible local emulator for Amazon EMR and AWS Glue. It sits in front of LocalStack, routes EMR and Glue AWS JSON 1.1 requests to dedicated emulators, and forwards every other AWS service without changing the request body.

The project targets:

- AWS CLI and AWS SDK compatibility through the documented wire protocols
- Amazon EMR cluster, bootstrap action, and step lifecycle emulation
- real Spark 3.5.x execution in local mode with LocalStack S3 access
- Glue Data Catalog behavior, including documented validation and service exceptions
- Spark 3.5.4 interoperability with Glue Data Catalog, Hive-compatible types, and Iceberg 1.7.1
- Docker images suitable for publishing to Amazon ECR

Glue Jobs, JobRuns, and Crawlers are intentionally out of scope. Compatibility is delivered incrementally and tracked in [the support scope](docs/support-scope.md) and [compatibility matrix](docs/compatibility/api-coverage.md).

## Quick start

```bash
cp .env.example .env
direnv allow          # optional
make bootstrap
make up
aws --endpoint-url http://localhost:4566 glue get-databases
```

Open `http://localhost:4566/_mystack/console` for the route, thread-stack, and asyncio-task
console. `make up CONFIG=path/in/repository.yaml` embeds the selected file in locally built
images; `compose.mount-config.yaml` optionally mounts a file read-only for live development or
prebuilt images. Use `MYSTACK__SECTION__KEY` only for deployment-specific overrides. See the
[configuration guide](docs/configuration.md) and [Docker Compose specification](https://docs.docker.com/reference/compose-file/).

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

## Status

The repository is under active construction. EMR currently exposes 13 boto3-tested operations,
and Glue exposes 22 boto3-tested Data Catalog operations. The baseline and
implementation-derived UseCase catalog live under [`docs/project`](docs/project).

Official behavior sources include the [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data), and [AWS Glue type-system documentation](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
