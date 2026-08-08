<!-- doc-id: extensions -->
<!-- lang: en -->

[한국어](extensions.ko.md) | [English](extensions.md)

# Glue extension SPI guide

Replace, wrap, or translate the error of one Glue operation without rebuilding
the Mystack image. Mount a Python wheel read-only and select its provider in
YAML. Extensions currently execute inside the Glue process and are not a sandbox
for untrusted code.

See the [tiered extension SPI ADR](adr/0003-tiered-extension-spis.md) for the
design decision.

<!-- section: tiers -->
## Three SPIs

| SPI | Use case | Access | Compatibility |
| --- | --- | --- | --- |
| `stable` | ordinary error corrections and policy additions | frozen snapshots and application-backed capabilities | maintained within SPI v1 |
| `application` | direct composition of domain use cases | `CatalogApplication` and public domain types | Mystack minor-version scope |
| `unsafe` | experiments, emergency repairs, storage inspection | repository, clock, settings, and application | exact Mystack version only |

Start with `stable`. `application` may return mutable domain objects, so its
`mystack_minor_version` must equal the installed `major.minor`. `unsafe` can bypass
invariants, so it requires both `allow_unsafe: true` and an exact `mystack_version`.

The composition root injects these boundaries following the [AWS hexagonal
architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html).
Domain and Application never know a user package.

<!-- section: chain -->
## Operation chain

Every SPI uses the same `OperationMiddleware` contract:

```python
class OperationMiddleware(Protocol):
    async def invoke(
        self,
        call: OperationCall,
        next_handler: OperationNext,
    ) -> Mapping[str, Any]: ...
```

- Code before `await next_handler(call)` is preprocessing.
- Changing its result is postprocessing.
- Catching and raising `AwsServiceError` translates an error.
- Returning a modeled response without calling next fully replaces behavior.
- One middleware may call its next handler only once.

Requests reach extensions after official botocore input validation. The final
success response is validated again against the official output model. Invalid
output fails safely as `InternalServiceException`. Derive AWS error behavior from
the operation's official contract, such as
[CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html).

<!-- section: package -->
## Create a provider package

Each SPI uses a separate entry-point namespace. Python discovers installed
distribution entry points with
[`importlib.metadata.entry_points`](https://docs.python.org/3/library/importlib.metadata.html#entry-points).
Metadata follows the [PyPA entry-points
specification](https://packaging.python.org/en/latest/specifications/entry-points/).

```toml
[project.entry-points."mystack.glue.extensions.stable.v1"]
my-correction = "my_extension:stable_provider"

[project.entry-points."mystack.glue.extensions.application.v1"]
my-application-extension = "my_extension:application_provider"

[project.entry-points."mystack.glue.extensions.unsafe.v1"]
my-unsafe-extension = "my_extension:unsafe_provider"
```

The entry-point callable receives its SPI context and returns
`OperationMiddleware`. A complete package lives under
`examples/glue-extension`. PyPA documents the same pattern in its [plugin
discovery guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/).

<!-- section: configuration -->
## YAML configuration

```yaml
glue:
  extensions:
    enabled: true
    allow_unsafe: true
    wheels_directory: /opt/mystack/extensions
    install_directory: /tmp/mystack/extensions
    install_timeout_seconds: 120
    providers:
      - id: my-stable-correction
        spi: stable
        api_version: 1
        entry_point: my-correction
        operations: [CreatePartition]
        priority: 100
        timeout_seconds: 5
      - id: my-application-extension
        spi: application
        api_version: 1
        entry_point: my-application-extension
        operations: [CreatePartition]
        priority: 200
        timeout_seconds: 5
        mystack_minor_version: "0.1"
      - id: my-unsafe-extension
        spi: unsafe
        api_version: 1
        entry_point: my-unsafe-extension
        operations: [CreatePartition]
        priority: 300
        timeout_seconds: 5
        mystack_version: 0.1.0
```

Lower priority is outer middleware. Equal priorities run in ID order.
`operations: ["*"]` is available, but explicit operation names are preferred for
reviewability.

Startup rejects duplicate IDs, unknown operations, unsupported API versions,
missing entry points, an `application` minor-version mismatch, disallowed unsafe access,
and an exact-version mismatch.

<!-- section: docker -->
## Run with Docker

Build the example wheel and enable `extensions` in the mounted YAML:

```bash
make extension-example
MYSTACK_GLUE_EXTENSIONS_DIR=./extensions \
docker compose \
  -f compose.yaml \
  -f compose.mount-config.yaml \
  -f compose.extensions.yaml \
  up --detach --wait
```

`compose.extensions.yaml` mounts the directory read-only under the [Docker
Compose volume specification](https://docs.docker.com/reference/compose-file/services/#volumes).
Container startup finds only `.whl` files. Pip runs with `--no-index --no-deps`,
so it neither resolves from the network nor changes Mystack's base environment.
Mount every required dependency wheel explicitly.

`make extension-e2e` does not depend on Docker Desktop host-directory sharing. A small seed image
uses [Docker volume copy-up
behavior](https://docs.docker.com/engine/storage/volumes/#mounting-a-volume-over-existing-data) to
populate an isolated named volume, which Glue mounts read-only.

<!-- section: diagnostics -->
## Logs and troubleshooting

Search these events by extension ID and SPI:

- `extension.install.*`: before, after, and failure around mounted wheel installation;
- `extension.provider.load.*`: entry-point discovery and context creation;
- `extension.invoke.*`: operation execution, service error, failure, and timeout;
- `protocol.output_validation.failed`: invalid plugin or built-in handler output.

Logs omit request values, wheel installer output, and credentials. `fix_hint`
identifies the configuration, entry point, provider, or output mapper to repair.

<!-- section: sources -->
## Official references

- [Python entry-point discovery](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [PyPA plugin discovery guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [PyPA entry-points specification](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Docker Compose volume specification](https://docs.docker.com/reference/compose-file/services/#volumes)
- [AWS Glue CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)
- [AWS hexagonal architecture guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
