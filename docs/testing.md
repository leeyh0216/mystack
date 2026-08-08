<!-- doc-id: testing -->
<!-- lang: en -->

[한국어](testing.ko.md) | [English](testing.md)

# Testing strategy

<!-- section: layers -->
## Layers

| Layer | Purpose | External runtime | Timeout source |
| --- | --- | --- | --- |
| Unit | Domain states, codecs, routing, configuration | None | `tests.unit_timeout_seconds` |
| Architecture | Inward-only imports and bounded contexts | None | unit timeout |
| Contract | boto3 serialization, response and modeled errors | API process | `tests.contract_timeout_seconds` |
| E2E | Public Proxy to LocalStack, EMR Spark, Glue Catalog, Hive/Iceberg | Docker | `tests.e2e_timeout_seconds` |

Every pytest invocation uses `pytest-timeout` with the thread method so a hang produces Python thread stacks. Spark/bootstrap adapters also receive service-specific process timeouts from YAML.

<!-- section: contracts -->
## Contract rules

- boto3 talks only to the public Proxy endpoint.
- Tests assert both successful results and modeled AWS error code/HTTP status/side effects.
- Every implemented operation receives boto3 coverage.
- Glue partition duplication must return `AlreadyExistsException`, following [CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html).
- One boto3 duplicate-partition contract proves stable, application, and unsafe contexts inspect
  the same managed state and compose one modeled error translation.
- Extension chain tests cover ordering, replacement, single-use next, configured timeouts,
  startup permission/version failures, and final output-model validation.
- EMR tests poll documented states rather than sleeping fixed durations; lifecycle follows the [EMR cluster model](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html).

<!-- section: e2e -->
## Real-runtime E2E

- Upload bootstrap/application/input data through boto3 S3 to LocalStack.
- Create and inspect EMR resources through boto3.
- Wait with a configured deadline and preserve logs on all failures.
- Verify S3A output and step state for real Python and Java JAR Spark 3.5.x applications, including
  cancellation while the subprocess is running. JAR submission follows Spark's official
  [`spark-submit --class` contract](https://spark.apache.org/docs/3.5.4/submitting-applications.html).
- Exercise all 13 implemented EMR and all 22 implemented Glue operations through the public
  Proxy boundary; the same reusable Glue scenario also runs directly against the Glue service.
- Exercise Glue Catalog through boto3 and Spark Hive/Iceberg adapters.
- The current Iceberg scenario covers create, append, read, and schema evolution. Partition and transaction scenarios remain target scope, using the [AWS Glue Iceberg contract](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html).

<!-- section: reproducibility -->
## Reproducibility

The lockfile, hash-locked container exports, YAML runtime profile, immutable container-base
digests, botocore manifest, Spark checksum/version, and Iceberg version are test inputs. Updating
any one requires corresponding manifest/profile documentation and E2E evidence. CI rejects a
`requirements/*.txt` export that does not match `uv.lock`; generation follows the official
[uv export command](https://docs.astral.sh/uv/reference/cli/#uv-export).

<!-- section: differential -->
## Optional differential layer

Real-AWS comparisons are read-only, normalized, file-configured, and disabled by default. Run
`MYSTACK_REAL_AWS_DIFFERENTIAL=1 uv run pytest -m differential --timeout 60` only in an explicitly
authorized AWS environment. SDK and pytest deadlines remain configurable; ordinary local and CI
contracts collect these cases as skips and require no cloud credentials.

AWS recommends automated independent core and E2E behavior tests for hexagonal systems in its [best-practices guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html).
