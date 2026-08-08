<!-- doc-id: configuration -->
<!-- lang: en -->

[한국어](configuration.ko.md) | [English](configuration.md)

# Configuration and reproducible containers

Mystack keeps runtime behavior in the versioned `config/mystack.yaml` document. The application
does not contain fallback service endpoints, credentials, release mappings, process deadlines,
Spark submit parsing tables, route registrations, or test deadlines. Docker's official guidance
distinguishes image build arguments, runtime environment variables, read-only configs, and
secrets; Mystack uses each only at its corresponding boundary. See [Docker build variables](https://docs.docker.com/build/building/variables/),
[Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/),
and [Compose configs](https://docs.docker.com/reference/compose-file/configs/).

<!-- section: resolution -->
## Resolution order

1. `--config PATH`, then `MYSTACK_CONFIG_FILE`, then `config/mystack.yaml` selects the base file.
2. Every `MYSTACK__SECTION__KEY` environment variable replaces that nested YAML value. Its value
   is parsed as YAML, so numbers, booleans, lists, mappings, and `null` keep their types.
3. Process-only `--host` and `--port` options override the selected service listener.

Examples:

```bash
MYSTACK_CONFIG_FILE=config/mystack.yaml \
MYSTACK__LOGGING__LEVEL=DEBUG \
MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600 \
mystack-proxy
```

Sensitive override paths are redacted in logs. Do not put production credentials or management
tokens in a committed YAML file; inject them at deployment time. Docker documents the difference
between ordinary environment configuration and [secrets](https://docs.docker.com/compose/how-tos/use-secrets/).

<!-- section: docker-modes -->
## Docker modes

The normal user command uses `compose.ghcr.yaml`. Each published image contains the reviewed
`/etc/mystack/mystack.yaml` from the same release, so no repository clone or config mount is needed.
`MYSTACK_IMAGE_TAG` is required and component-specific full image references can be supplied through
`MYSTACK_PROXY_IMAGE`, `MYSTACK_EMR_IMAGE`, and `MYSTACK_GLUE_IMAGE` for digest pinning. Keep the tag
defined even when all three overrides are present because Compose evaluates nested fallbacks.

To customize a published deployment, download `config/mystack.yaml` and
`compose.mount-config.yaml` from the same Git tag as the images, then mount the file read-only:

```bash
MYSTACK_CONFIG_FILE="$PWD/mystack.yaml" \
docker compose -f compose.ghcr.yaml -f compose.mount-config.yaml up --detach --wait
```

Restart the affected container after editing the mounted file. Configuration is intentionally
loaded once at process startup; no partially applied hot reload is performed.

Repository maintainers can use `make up CONFIG=config/mystack.yaml`; that source-build path passes
`MYSTACK_CONFIG_SOURCE` as a build argument. It is documented in the [development guide](development.md)
and is not required for image consumers.

<!-- section: sections -->
## Main sections

| Path | Responsibility |
| --- | --- |
| `logging` | Structured log level and format contract |
| `management.diagnostics` | Enablement, bearer token, and maximum thread/task stack depth |
| `proxy` | Listener, fallback, outbound timeout, and extensible route registry |
| `localstack` | S3 endpoint, region, account, local credentials, and path-style behavior |
| `emr` | Work storage, deadlines, process policy, release profiles, and operation limits |
| `glue` | Durable catalog state, catalog ID, paging, and runtime profile |
| `runtime_profiles` | Spark command, master, packages, conf, parser options, and Glue versions |
| `tests` | Unit/contract/E2E/Compose deadlines and black-box client/runtime settings |

New settings must be added to the YAML, mapped by the relevant composition-root configuration
adapter, covered by a typed configuration test, and documented in both languages. Inner Domain
and Application modules receive typed policy/value objects and never read files or environment
variables.

`emr.shutdown_timeout_seconds` bounds service shutdown after scheduling has stopped. Within that
deadline, EMR cancels and awaits owned driver tasks, terminates or kills bootstrap/Spark children
using `emr.terminate_grace_seconds`, and closes the lifecycle-owned log publisher and artifact
clients. It is distinct from the
per-bootstrap and per-Step execution deadlines. Python documents the underlying behavior in
[`asyncio.wait_for`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for).

The EMR image always runs bootstrap and Spark processes as `hadoop`; the persistent Ivy mount is
`/home/hadoop/.ivy2`. A bootstrap-created virtualenv must live in a path readable by that user and a
later Step must select it through `spark.pyspark.python` and `spark.pyspark.driver.python`. The
runtime profile controls the allowed submit aliases and options; the artifact adapter materializes
the primary application and `--py-files`, `--files`, `--jars`, and `--archives` remote resources.
Amazon EMR documents the [Hadoop bootstrap identity](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
and Spark documents these [submission options](https://spark.apache.org/docs/3.5.4/submitting-applications.html).

S3 log publication has no separate hard-coded bucket or prefix. Each cluster supplies the standard
`RunJobFlow.LogUri`; the publisher reuses `localstack.endpoint_url`, region, credentials, and
path-style setting. This keeps image deployments configurable and lets the same boto3 S3 route
reach LocalStack. See the [exact log protocol](protocols/emr-log-layout.md).

`emr.startup_clusters_file` is either `null` or a path to a separate schema-versioned document.
Relative paths resolve beside the selected main configuration. The file uses official
[`RunJobFlow` members](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html) and
is fully validated before any side effect. The optional
`compose.emr-startup-clusters.yaml` overlay performs an explicit read-only
[bind mount](https://docs.docker.com/engine/storage/bind-mounts/). See the [startup cluster
protocol](protocols/emr-startup-clusters.md) for its allowlist and restart semantics.

The E2E harness resolves the EMR route from `tests.emr_service` and copies the prebuilt Java
fixture from `tests.emr_jar_fixture_container_path`. Both are configuration values so a renamed
Compose service or custom runtime image needs no test-code change. Spark documents JAR and main
class submission in its official [application submission guide](https://spark.apache.org/docs/3.5.4/submitting-applications.html).
Browser interaction deadlines and whether missing Chromium is fatal are configured by
`tests.e2e.browser_action_timeout_seconds` and the environment variable named by
`tests.e2e.browser_required_environment_variable`.
The isolated wheel co-installation deadline is `tests.package_smoke_timeout_seconds`.

After environment overrides, every process validates the complete document against the packaged
[`mystack.schema.json`](../shared/src/mystack/aws_protocol/mystack.schema.json). Unknown keys,
missing members, invalid URLs/account IDs/ports, and non-positive deadlines fail before startup
with the exact dotted path. The schema uses the official
[JSON Schema 2020-12 specification](https://json-schema.org/draft/2020-12/json-schema-core).

<!-- section: reproducibility -->
## Reproducible build inputs

- `uv.lock` is the development dependency lock.
- `requirements/{proxy,emr,glue}.txt` are hash-locked exports generated by `make requirements`.
- CI runs `scripts/export_requirements.py --check` so the exports cannot drift from `uv.lock`.
- Container bases use immutable multi-architecture digests by default; Compose variables can
  deliberately select another digest.
- Spark downloads are version arguments and pass the published SHA-512 check.
- Runtime-profile versions and real Spark/Hive/Iceberg E2E assertions detect an image/config
  mismatch.

The export mechanism follows the official [uv export interface](https://docs.astral.sh/uv/reference/cli/#uv-export).
