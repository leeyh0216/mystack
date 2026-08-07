# Mystack

Mystack is a protocol-compatible local emulator for Amazon EMR and AWS Glue. It sits in front of LocalStack, routes EMR and Glue AWS JSON 1.1 requests to dedicated emulators, and forwards every other AWS service without changing the request body.

The project targets:

- AWS CLI and AWS SDK compatibility through the documented wire protocols
- Amazon EMR cluster, bootstrap action, and step lifecycle emulation
- real Spark 3.5.x execution in local mode with LocalStack S3 access
- AWS Glue 5.0 jobs on Spark 3.5.4 and the official Glue local runtime image
- Glue Data Catalog behavior, including documented validation and service exceptions
- Hive-compatible types and Apache Iceberg integration
- Docker images suitable for publishing to Amazon ECR

Glue Crawlers are intentionally out of scope. Compatibility is delivered incrementally and tracked in [the compatibility matrix](docs/compatibility/api-coverage.md).

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

See [architecture.md](docs/architecture.md) and [AWS protocol analysis](docs/protocols/aws-json-1.1.md) for the detailed contracts.

## Status

The repository is under active construction. The baseline and implementation-derived UseCase catalog live under [`docs/project`](docs/project).

