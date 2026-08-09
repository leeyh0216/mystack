<!-- doc-id: operations-guide -->
<!-- lang: en -->

[한국어](operations.ko.md) | [English](operations.md)

# Operations

<!-- toc:start -->
## Contents

- [Open the service UIs](#open-the-service-uis)
- [Inspect health, logs, and diagnostics](#inspect-health-logs-and-diagnostics)
- [Mount a configuration file](#mount-a-configuration-file)
- [Upgrade, roll back, or clean up](#upgrade-roll-back-or-clean-up)
- [Official sources](#official-sources)
<!-- toc:end -->

Use this page to inspect a running stack, work with the service-owned UIs, change a mounted
configuration file, or stop a local environment.

<!-- section: ui -->
## Open the service UIs

Open the EMR UI to create clusters, submit and follow Steps, inspect the submitted command vector,
and read live or published logs.

```text
http://localhost:4566/_mystack/ui/emr/
```

Open the Glue UI to browse databases, tables, schemas, partitions, parameters, and raw metadata.

```text
http://localhost:4566/_mystack/ui/glue/
```

Resource selections are represented by the URL. You can refresh, use browser history, or share a
link to a selected cluster, Step, table, or partition. For the UI route and streaming contract, see
the [management UI reference](console.md).

<!-- section: diagnostics -->
## Inspect health, logs, and diagnostics

Run these commands from the directory that contains `compose.ghcr.yaml`.

```bash
docker compose -f compose.ghcr.yaml ps
docker compose -f compose.ghcr.yaml logs --tail 200 proxy glue emr
curl --fail http://localhost:4566/_mystack/routes
curl --fail http://localhost:4566/_mystack/diagnostics/threads
curl --fail http://localhost:4566/_mystack/diagnostics/tasks
```

Use the EMR Step page first for application stdout, stderr, command arguments, and S3 log
publication. Use service logs and the diagnostics endpoints when a request or subprocess is stuck.
The [observability guide](observability.md) describes event fields and troubleshooting boundaries.

<!-- section: configuration -->
## Mount a configuration file

Download the configuration and matching Compose overlay for the image version you are running,
then mount the file read-only for all Mystack services.

```bash
curl --fail --location --output mystack.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/config/runtime/mystack.yaml"
curl --fail --location --output compose.mount-config.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.mount-config.yaml"

export MYSTACK_CONFIG_FILE="$PWD/mystack.yaml"
docker compose \
  -f compose.ghcr.yaml \
  -f compose.mount-config.yaml \
  up --detach --wait --wait-timeout 300
```

Restart the affected service after changing the mounted file. Use the
[configuration reference](configuration.md) for setting names, override precedence, and timeout
values.

<!-- section: lifecycle -->
## Upgrade, roll back, or clean up

To upgrade or roll back, set `MYSTACK_IMAGE_TAG` to the intended version, download the matching
`compose.ghcr.yaml`, then pull and recreate the stack.

```bash
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
```

Use the same commands with a previously verified version to roll back. These shutdown commands
have different data effects:

```bash
docker compose -f compose.ghcr.yaml stop
docker compose -f compose.ghcr.yaml down
docker compose -f compose.ghcr.yaml down --volumes
```

`stop` preserves containers and data. `down` removes containers while retaining named volumes.
`down --volumes` permanently removes EMR, Glue, and LocalStack state.

<!-- section: sources -->
## Official sources

- [Docker Compose command reference](https://docs.docker.com/reference/cli/docker/compose/)
- [Docker Compose file merge](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Amazon EMR log files](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)
