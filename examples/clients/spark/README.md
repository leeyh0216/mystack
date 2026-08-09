# Spark client lab

Run a local Spark Hive and Iceberg round trip through Mystack's public Proxy. Compose starts
Mystack, LocalStack S3, and a separate client using the pinned Glue 5 / Spark 3.5 runtime. The
Spark program creates Hive and Iceberg namespaces and tables, writes data, and reads it back.
No AWS account or cloud credentials are required.

## Prerequisites

- Docker Desktop (or Docker Engine) is running.
- Docker Compose v2 supports [`include`](https://docs.docker.com/reference/compose-file/include/).
- Run the commands from this directory, not the repository root.

## Run the lab

Copy and paste this block. The first execution can take several minutes because it builds the
client image and resolves Spark's Maven/Ivy dependencies.

```bash
cd examples/clients/spark
docker compose config --quiet
docker compose up --build --abort-on-container-exit --exit-code-from spark-client
```

`spark-client` exits with status `0` when the Hive and Iceberg workflow succeeds. Mystack services
remain available after the client exits.

## Check the result

The final Spark output includes one result with a row count for each table:

```text
{'hive_database': 'client_lab_hive', 'hive_count': 1, 'iceberg_database': 'client_lab_iceberg', 'iceberg_count': 1}
```

Use these commands to inspect the result and service health:

```bash
# Print the completed Spark client output.
docker compose logs spark-client

# Confirm the Proxy and LocalStack services are healthy.
docker compose ps

# Query the public health endpoint from the host.
curl --fail http://localhost:4566/_mystack/health
```

To run the same client program again while the stack is up:

```bash
docker compose run --rm spark-client \
  --master local[2] \
  /workspace/verify.py
```

## Clean up

Stop the lab and remove its containers, network, and local volumes:

```bash
docker compose down --volumes --remove-orphans
```

The workload is [`verify.py`](verify.py); [`run.sh`](run.sh) creates the S3 bucket before Spark
starts. See [client workflows](../../../docs/client-workflows.md) for the Hive/Iceberg API path and
the compatibility matrix for the exact support boundary.
