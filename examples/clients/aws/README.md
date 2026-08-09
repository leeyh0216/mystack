# AWS client lab

Run a complete local `boto3` and AWS SDK for pandas workflow with no AWS account or cloud
credentials. Compose starts Mystack, LocalStack S3, and the `aws-client` container. The client
uses Mystack's public Proxy for Glue, EMR, and S3-compatible requests, then:

1. creates an S3 bucket and Glue database;
2. writes partitioned Parquet data with `awswrangler`;
3. reads the Glue table; and
4. calls EMR `ListClusters`.

## Prerequisites

- Docker Desktop (or Docker Engine) is running.
- Docker Compose v2 supports [`include`](https://docs.docker.com/reference/compose-file/include/).
- Run the commands from this directory, not the repository root.

## What Compose runs

| File | Role when you run the lab |
| --- | --- |
| [`compose.yaml`](compose.yaml) | Includes the repository stack, waits for the public `proxy` to become healthy, and defines the `aws-client` container with local test credentials and `AWS_ENDPOINT_URL=http://proxy:8080`. |
| [`compose.env`](compose.env) | Sets `MYSTACK_PORT=0`, so this lab does not claim the host's usual `4566` port. Containers communicate over the internal Compose network. |
| [`Dockerfile`](Dockerfile) | Builds the small Python client image, installs the pinned packages in `requirements.txt`, and makes `verify.py` its default command. |
| [`verify.py`](verify.py) | The executable workload: creates `mystack-client-lab` and `client_lab`, writes a two-row partitioned `events` Parquet dataset with `awswrangler`, reads its Glue table, then calls EMR `ListClusters` and prints the result. |
| [`requirements.txt`](requirements.txt) | Pins `boto3`, `awswrangler`, and `pandas` used by the workload. |

The command `docker compose up … --exit-code-from aws-client` uses `verify.py` as the success
signal: a nonzero exit means one of those API calls or the data write/read failed.

## Run the lab

Copy and paste this block. The first run downloads and builds the client image.

```bash
cd examples/clients/aws
docker compose config --quiet
docker compose up --build --abort-on-container-exit --exit-code-from aws-client
```

`aws-client` exits with status `0` when the workflow succeeds. The long-running Mystack services
remain available after the client exits.

## Check the result

The final client log must include a result like this (the EMR count can vary):

```text
{'glue_database': 'client_lab', 'glue_table': 'events', 'emr_cluster_count': 0}
```

Use these commands to inspect the completed workload or the services:

```bash
# Print only the client result again.
docker compose logs aws-client

# Confirm the Proxy and LocalStack services are healthy.
docker compose ps

# Query the public health endpoint from the host.
curl --fail http://localhost:4566/_mystack/health
```

To repeat the workflow without deleting the lab data, start a new one-off client container:

```bash
docker compose run --rm aws-client python verify.py
```

## Clean up

Stop the lab and remove its containers, network, and local volumes:

```bash
docker compose down --volumes --remove-orphans
```

See [client workflows](../../../docs/client-workflows.md) for the API path, supported scope, and
production-client configuration.
