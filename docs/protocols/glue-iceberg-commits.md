<!-- doc-id: protocols/glue-iceberg-commits -->
<!-- lang: en -->

[한국어](glue-iceberg-commits.ko.md) | [English](glue-iceberg-commits.md)

# Iceberg GlueCatalog commit contract

This contract defines the catalog-pointer portion of Apache Iceberg 1.7.1 commits against the
Mystack Glue emulator. AWS Glue 5.0 includes Iceberg 1.7.1 and uses optimistic locking by default;
the Iceberg AWS integration uses Glue table `VersionId` to reject a stale metadata-pointer swap and
then refresh/retry. See the [AWS Glue Iceberg guide](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
and [Iceberg AWS optimistic-locking contract](https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking).

<!-- section: responsibility -->
## Responsibility boundary

Mystack implements the Glue catalog operation, not the Iceberg table format. Spark/Iceberg writes
data, manifests, metadata JSON, snapshots, and S3 objects through Iceberg's own implementation.
Mystack stores the `TableInput` supplied to `UpdateTable`, including `Parameters.metadata_location`,
and atomically changes the current catalog pointer when its expected `VersionId` is current. It does
not parse or rewrite Iceberg metadata files.

This split follows Iceberg's [reliability model](https://iceberg.apache.org/docs/1.7.1/reliability/#concurrent-write-operations):
writers prepare independent metadata and use an atomic current-metadata pointer swap to commit.

<!-- section: algorithm -->
## Atomic decision and persistence order

One durable update uses this order:

1. The AWS JSON 1.1 boundary validates the modeled `UpdateTable` request.
2. The repository acquires its process-local asynchronous mutex and the configured POSIX advisory
   file lock.
3. While holding both locks, it reloads the latest JSON catalog revision from disk.
4. The application resolves the table and compares the request `VersionId` with its current value.
5. A matching writer builds exactly one candidate: the supplied table definition becomes current,
   the integer version advances once, and the prior version is archived unless `SkipArchive=true`.
6. The repository writes a same-directory temporary document, fsyncs it, atomically replaces the
   state file, attempts directory fsync, and only then publishes the candidate as visible state.
7. It releases the file lock and then the process-local mutex.

A stale writer raises modeled `ConcurrentModificationException` before save. A validation, conflict, or
persistence failure never publishes its candidate. Cancellation while a save is in progress waits
for the bounded save result before deciding whether the committed candidate is visible. Lock
acquisition and release also shield their worker thread so cancellation cannot leave a descriptor
locked.

Two processes committing from the same base version therefore produce one version-1 winner and one
stale-version failure. An Iceberg client may refresh the new pointer and retry its independent
change. This is catalog compare-and-swap, not global transaction isolation for S3 data files.

<!-- section: configuration -->
## File-lock configuration

`glue.catalog_lock.file`, `acquire_timeout_seconds`, and `poll_interval_seconds` are required YAML
settings. Relative paths resolve under `glue.data_root`. The lock file must differ from
`glue.state_file`, the poll interval must not exceed the acquisition timeout, and all Glue emulator
processes sharing one state file must use the same lock file on a filesystem that honors POSIX
`flock`. Python documents this primitive in [`fcntl.flock`](https://docs.python.org/3/library/fcntl.html#fcntl.flock).

The lock wait is bounded. A timeout fails the operation without changing state. The lock file is
retained rather than deleted because unlink/recreate can split concurrent processes across
different inodes. This implementation supports Docker/Linux and local POSIX hosts; multi-host
distributed locking and filesystems without reliable advisory locks are outside the contract.

<!-- section: observability -->
## Logging and repair locations

`glue.iceberg.commit.begin`, `.version.accepted`, `.persist.before`, `.conflict`, `.succeeded`, and
`.failed` expose the expected/current/candidate version and only SHA-256 prefixes for resource and
metadata location. They never contain the S3 path, table body, credentials, or authorization
headers. `glue.repository.process_lock.*`, `.external_state.refresh.after`, `.transaction.*`, and
`.persist.*` show the lock/reload/save boundary.

When an upgraded Spark/Iceberg client breaks this path:

1. Missing or changed wire members belong in the pinned botocore model boundary and
   `glue/adapters/inbound/aws_table.py`.
2. `VersionId`, archive, or `SkipArchive` decisions belong in `CatalogTable.revise` and
   `glue/application/table.py`.
3. Iceberg identification and safe commit events belong in
   `glue/application/iceberg_commit.py`.
4. Cross-process lost updates, lock timeouts, reload, fsync, or replacement belong in
   `glue/adapters/outbound/repository.py` and `glue.catalog_lock` configuration.
5. Real-client retry drift belongs in `glue/scripts/e2e/iceberg_contention_job.py` and the generated
   compatibility case.

<!-- section: evidence -->
## Evidence and exclusions

The fast contract `glue/tests/test_iceberg_commit.py` starts two spawned processes from one base
version, enforces configurable waits, and checks one winner, one conflict, valid JSON, archive
policy, and bounded lock timeout. CI additionally starts two separate Glue-image containers, runs
real Spark 3.5.4/Iceberg 1.7.1 writers through the public Proxy, and requires both retried appends to
remain visible. Docker Compose defines the one-off container behavior in its
[`run` reference](https://docs.docker.com/reference/cli/docker/compose/run/).
Partition, schema, sort, and identifier evolution reuse this exact pointer commit and are verified
by the separate [Iceberg evolution contract](glue-iceberg-evolution.md).
Row-level COW/MOR commits reuse it as verified by the
[Iceberg row-level DML contract](glue-iceberg-row-level-dml.md).
Snapshot/reference/procedure commits reuse it as verified by the
[Iceberg snapshot/reference/procedure contract](glue-iceberg-snapshots-refs-procedures.md).
Rename/drop/purge uses it as described by the
[Iceberg lifecycle contract](glue-iceberg-lifecycle.md).

This contract does not itself define Iceberg SQL semantics. Managed optimizers,
Open Table Format inputs are covered by the separate [input contract](glue-open-table-format.md).
Lake Formation, authentication, cross-account/cross-Region behavior, PyIceberg, Flink, and Trino
are excluded.

<!-- section: sources -->
## Official sources

- [AWS Glue: Using the Iceberg framework](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 AWS integration](https://iceberg.apache.org/docs/1.7.1/aws/)
- [Apache Iceberg 1.7.1 reliability](https://iceberg.apache.org/docs/1.7.1/reliability/)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `TableVersion`](https://docs.aws.amazon.com/glue/latest/webapi/API_TableVersion.html)
- [Python `fcntl`](https://docs.python.org/3/library/fcntl.html)
