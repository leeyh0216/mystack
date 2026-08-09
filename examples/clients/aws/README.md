# AWS client lab

This lab starts Mystack plus one Python client container. The client uses the public Proxy for
Glue, EMR, and S3-compatible requests; it creates a bucket/database, writes a partitioned Parquet
dataset with AWS SDK for pandas, reads its Glue table, and calls EMR `ListClusters`.

```bash
docker compose up --build --abort-on-container-exit --exit-code-from aws-client
```

Expected output contains `glue_table: 'events'` and an EMR cluster count. Stop persistent services
afterward with `docker compose down --volumes`.

See [client workflows](../../../docs/client-workflows.md) for the API path and scope.
