# Testing strategy

[한국어](testing.ko.md) | English

## Layers

| Layer | Purpose | External runtime | Timeout source |
| --- | --- | --- | --- |
| Unit | Domain states, codecs, routing, configuration | None | `tests.unit_timeout_seconds` |
| Architecture | Inward-only imports and bounded contexts | None | unit timeout |
| Contract | boto3 serialization, response and modeled errors | API process | `tests.contract_timeout_seconds` |
| E2E | Public Proxy to LocalStack, EMR Spark, Glue Catalog, Hive/Iceberg | Docker | `tests.e2e_timeout_seconds` |

Every pytest invocation uses `pytest-timeout` with the thread method so a hang produces Python thread stacks. Spark/bootstrap adapters also receive service-specific process timeouts from YAML.

## Contract rules

- boto3 talks only to the public Proxy endpoint.
- Tests assert both successful results and modeled AWS error code/HTTP status/side effects.
- Every implemented operation receives boto3 coverage.
- Glue partition duplication must return `AlreadyExistsException`, following [CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html).
- EMR tests poll documented states rather than sleeping fixed durations; lifecycle follows the [EMR cluster model](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html).

## Real-runtime E2E

- Upload bootstrap/application/input data through boto3 S3 to LocalStack.
- Create and inspect EMR resources through boto3.
- Wait with a configured deadline and preserve logs on all failures.
- Verify output objects and step state after a real Spark 3.5.x process.
- Exercise Glue Catalog through boto3 and Spark Hive/Iceberg adapters.
- Iceberg scenarios cover create, append, read, partition behavior, and schema evolution, using the [AWS Glue Iceberg contract](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html).

## Reproducibility

The lockfile, YAML runtime profile, container base, botocore manifest, Spark version, and Iceberg version are test inputs. Updating any one requires corresponding manifest/profile documentation and E2E evidence.

AWS recommends automated independent core and E2E behavior tests for hexagonal systems in its [best-practices guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html).

