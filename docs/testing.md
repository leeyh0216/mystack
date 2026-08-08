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
| Frontend | Shared theme/primitives, React components, TypeScript, production assets | Node/jsdom | `MYSTACK_FRONTEND_TEST_TIMEOUT_MS` plus CI job timeout |
| Contract | boto3 serialization, response and modeled errors | API process | `tests.contract_timeout_seconds` |
| E2E | Public Proxy to LocalStack, EMR Spark, Glue Catalog, Hive/Iceberg, AWS SDK for pandas | Docker | `tests.e2e_timeout_seconds` |

Every pytest invocation uses `pytest-timeout` with the thread method so a hang produces Python thread stacks. Spark/bootstrap adapters also receive service-specific process timeouts from YAML. Vitest uses the explicit configurable millisecond deadline for both tests and hooks; CI separately bounds lint, type checking, tests, and production builds at the job level.

<!-- section: contracts -->
## Contract rules

- boto3 talks only to the public Proxy endpoint.
- Tests assert both successful results and modeled AWS error code/HTTP status/side effects.
- Every implemented operation receives boto3 coverage.
- Glue partition duplication must return `AlreadyExistsException`, following [CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html).
- One boto3 duplicate-partition contract proves stable, application, and unsafe contexts inspect
  the same managed state and compose one modeled error translation.
- EMR tests poll documented states rather than sleeping fixed durations; lifecycle follows the [EMR cluster model](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html).
- EMR lifecycle tests inject partial startup and driver failure, close the scheduler twice, and run a
  real child process to prove reverse-order cleanup, no task/process/lock leaks, and deadline use.
  Handler responsibility tests also pin the public cluster-command, Step-command, and query surfaces.
- Operation-family tests instantiate every EMR and Glue family without the service adapter, assert
  disjoint ownership, compare their union to the implemented compatibility coverage in both
  directions, and verify family-local modeled error translation. Generic registry mutation tests
  prove duplicate, missing, and unexpected handlers fail before request dispatch.

<!-- section: e2e -->
## Real-runtime E2E

- Upload bootstrap/application/input data through boto3 S3 to LocalStack; prove the bootstrap runs
  as `hadoop`, can use `sudo`, creates a virtualenv, and a later PySpark Step selects that interpreter.
- Create and inspect EMR resources through boto3.
- Start the image with a read-only versioned cluster file, discover its cluster through boto3 and
  the management boundary without calling `RunJobFlow`, restart EMR, and require one newly assigned
  ID. Unit contracts reject the complete plan before any command call when one entry is invalid.
- Start EMR through the read-only pre-start overlay, install a disposable CA in the OS/Python and
  copied Java truststores, verify lexical order and exported values in PID 1, a boto3-created
  bootstrap action, and a real Spark Step. Separate raw-container contracts require fail-fast
  exit-code preservation, no later script, final UID 10001, and signal-safe PID 1 shutdown. See the
  [pre-start contract](protocols/emr-prestart.md).
- Wait with a configured deadline and preserve logs on all failures.
- Verify S3A output and step state for real Python and Java JAR Spark 3.5.x applications, including
  primary/dependency artifact materialization and cancellation while the subprocess is running. JAR
  submission follows Spark's official
  [`spark-submit --class` contract](https://spark.apache.org/docs/3.5.4/submitting-applications.html).
- Verify through the public Proxy that successful, failed-preparation, and cancelled Steps publish
  the exact gzip Step/application key set to LocalStack S3 and that the management API exposes the
  same publication evidence. The layout follows the [official EMR log paths](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html).
- Exercise all 13 implemented EMR and all 22 implemented Glue operations through the public
  Proxy boundary; the same reusable Glue scenario also runs directly against the Glue service.
- Exercise Glue Catalog through boto3 and Spark Hive/Iceberg adapters.
- Inject Glue state-store failure, cancellation, concurrent writers, stale table versions, restart,
  rename/cascade, and schema-1 migration. These contracts prove Data Catalog metadata atomicity;
  they do not claim the separate Iceberg table-transaction target is complete.
- Mutate Glue input/output dictionaries around domain construction and assert that names, table
  revision/archive/CAS, partition cardinality, and aggregate moves remain immutable. Executable
  responsibility tests restrict every handler and repository to its documented public methods.
- Exercise partitioned Parquet write/read, S3 HEAD, and Glue table/partition metadata through the
  same public Proxy with AWS SDK for pandas 3.17.0. The [client compatibility
  matrix](compatibility/client-matrix.md) records the exact scope.
- Drive both service-owned React UIs through Proxy with Playwright: create/terminate an EMR cluster, submit, track,
  cancel and inspect a Step, verify S3 log publication, explore a complex Glue schema and partition,
  and assert keyboard/ARIA behavior plus a clean browser console. Browser actions use
  `tests.e2e.browser_action_timeout_seconds`; CI makes Chromium execution mandatory through the
  configured environment-variable name. Playwright's official
  [auto-waiting behavior](https://playwright.dev/python/docs/actionability) remains bounded by that
  explicit deadline.
- Restart the EMR Compose service while a long Step is running, then verify the recovered Console
  projection, preserved stdout, modeled boto3 not-found behavior, and idempotently republished S3
  archive. The Compose subprocess and every HTTP/SDK wait use the configured E2E timeout. Docker's
  official [`compose restart` contract](https://docs.docker.com/reference/cli/docker/compose/restart/)
  defines the injected lifecycle event.
- The current Iceberg scenario covers create, append, read, and schema evolution. Partition and transaction scenarios remain target scope, using the [AWS Glue Iceberg contract](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html).

<!-- section: reproducibility -->
## Reproducibility

The `uv.lock` and `package-lock.json` lockfiles, hash-locked container exports, YAML runtime profile, immutable container-base
digests, botocore manifest, Spark checksum/version, and Iceberg version are test inputs. Updating
any one requires corresponding manifest/profile documentation and E2E evidence. CI rejects a
`requirements/*.txt` export that does not match `uv.lock`; generation follows the official
[uv export command](https://docs.astral.sh/uv/reference/cli/#uv-export).
The frontend gate runs ESLint, `tsc` project references, Vitest, and both Vite builds. A shared-theme
contract proves both applications consume the same semantic CSS variables, while the Docker E2E
proves each final service image serves its own built assets and Proxy preserves the stable paths.

<!-- section: local-contracts -->
## Local compatibility authority

Mystack never calls a real AWS account to compare behavior. Official AWS API documentation and the
pinned botocore models define operations, shapes, constraints, and declared errors. When the
documents do not define which of several invalid conditions wins, a reviewed internal validation
order defines the first failure. Parameterized local contracts make every catalog-state error
reproducible; configured fault injection covers documented internal and timeout failures that have
no natural state trigger. Authentication and authorization errors are outside the project scope.
The focused [partition/batch error contract](protocols/glue-partition-batch-errors.md) covers modeled
maximum constraints, validation order, stable partial success, `UnprocessedKeys`, and persistence
rollback without starting Docker.

AWS recommends automated independent core and E2E behavior tests for hexagonal systems in its [best-practices guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html).
