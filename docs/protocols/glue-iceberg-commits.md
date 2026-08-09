<!-- doc-id: protocols/glue-iceberg-commits -->
<!-- lang: en -->

[한국어](glue-iceberg-commits.ko.md) | [English](glue-iceberg-commits.md)

# Iceberg GlueCatalog commit contract

<!-- toc:start -->
## Contents

- [Responsibility boundary](#responsibility-boundary)
- [Atomic decision and persistence order](#atomic-decision-and-persistence-order)
- [SQLite transaction configuration](#sqlite-transaction-configuration)
- [Logging and repair locations](#logging-and-repair-locations)
- [Evidence and exclusions](#evidence-and-exclusions)
- [Official sources](#official-sources)
<!-- toc:end -->

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
2. A short-lived SQLite connection applies the configured foreign-key, journal, synchronous, and
   busy-timeout policy, then starts `BEGIN IMMEDIATE`.
3. The application resolves the current normalized table row and compares the request `VersionId`
   with its current value.
4. A matching writer builds exactly one candidate: the supplied table definition becomes current,
   the integer version advances once, and the prior version is archived unless `SkipArchive=true`.
5. The adapter conditionally updates the current table with the old `VersionId`, writes archive and
   partition-key rows in the same transaction, increments the diagnostic catalog revision, and
   commits.
6. It closes the connection. A failed validation, conditional update, or commit rolls the entire
   SQLite transaction back.

A stale writer raises modeled `ConcurrentModificationException` before save. A validation, conflict, or
persistence failure never publishes its candidate. Cancellation while a commit is in progress waits
for the bounded commit result before deciding whether the durable candidate is visible.

Two processes committing from the same base version therefore produce one version-1 winner and one
stale-version failure. An Iceberg client may refresh the new pointer and retry its independent
change. This is catalog compare-and-swap, not global transaction isolation for S3 data files.

<!-- section: configuration -->
## SQLite transaction configuration

`glue.sqlite.database_file` is the only durable catalog path. Its parent directory must be mounted
writable because WAL retains `-wal` and `-shm` siblings. `busy_timeout_milliseconds` bounds one
busy writer wait; `retry_limit` bounds additional short retries. A contention timeout fails the
request without committing a partial change. `journal_mode: wal` is the verified default;
`journal_mode: rollback` is an explicit escape hatch and never an automatic fallback.

SQLite WAL supports concurrent readers and one writer on one host using the same mounted directory.
Multi-host deployment and network filesystems are outside this contract. The complete driver gate,
backup procedure, checkpoint policy, and mounted configuration are defined by the
[Glue SQLite runtime contract](glue-sqlite-runtime.md).

<!-- section: observability -->
## Logging and repair locations

`glue.iceberg.commit.begin`, `.version.accepted`, `.persist.before`, `.conflict`, `.succeeded`, and
`.failed` expose the expected/current/candidate version and only SHA-256 prefixes for resource and
metadata location. They never contain the S3 path, table body, credentials, or authorization
headers. `glue.sqlite_catalog.schema.*`, `.transaction.begin.*`, `.transaction.busy.retry`,
`.transaction.commit.*`, and `.transaction.rolled_back` show the catalog storage boundary.

When an upgraded Spark/Iceberg client breaks this path:

1. Missing or changed wire members belong in the pinned botocore model boundary and
   `glue/adapters/inbound/aws_table.py`.
2. `VersionId`, archive, or `SkipArchive` decisions belong in `CatalogTable.revise` and
   `glue/application/table.py`.
3. Iceberg identification and safe commit events belong in
   `glue/application/iceberg_commit.py`.
4. Cross-process lost updates, writer contention, schema mapping, or commit/rollback belong in
   `glue/adapters/outbound/sqlite_catalog/` and `glue.sqlite` configuration.
5. Real-client retry drift belongs in `glue/tests/workloads/iceberg_contention_job.py` and the generated
   compatibility case.

<!-- section: evidence -->
## Evidence and exclusions

The fast contract `glue/tests/test_iceberg_commit.py` starts two spawned processes from one base
version, enforces configurable waits, and checks one winner, one conflict, foreign-key integrity,
archive policy, and bounded SQLite writer contention. CI additionally starts two separate Glue-image containers, runs
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
- [SQLite transactions](https://www.sqlite.org/lang_transaction.html)
- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
