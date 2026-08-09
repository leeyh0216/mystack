# Spark client lab

This lab starts Mystack and a separate Spark client process in the Glue 5/Spark 3.5 runtime. The
client executes the same public-Proxy Hive and Iceberg catalog scenario used for compatibility
testing: it creates Hive and Iceberg namespaces/tables, writes and reads Parquet/Iceberg data in
LocalStack S3, and prints `MYSTACK_E2E_RESULT=` on success.

```bash
docker compose up --build --abort-on-container-exit --exit-code-from spark-client
```

The initial image build and Maven/Ivy resolution can take several minutes. Stop persistent services
afterward with `docker compose down --volumes`.

See [client workflows](../../../docs/client-workflows.md) for the Spark Hive/Iceberg request path
and the compatibility matrix for its exact support boundary.
