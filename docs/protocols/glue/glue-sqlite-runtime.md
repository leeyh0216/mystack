<!-- doc-id: protocols/glue/glue-sqlite-runtime -->
<!-- lang: en -->

[한국어](glue-sqlite-runtime.ko.md) | [English](glue-sqlite-runtime.md)

# Glue SQLite runtime contract

<!-- toc:start -->
## Contents

- [Index](#index)
- [Runtime boundary](#runtime-boundary)
- [Configuration](#configuration)
- [Startup verification](#startup-verification)
- [Storage operations](#storage-operations)
- [Observability and repair](#observability-and-repair)
- [Official sources](#official-sources)
<!-- toc:end -->

<!-- section: index -->
## Index

- [Runtime boundary](#runtime-boundary)
- [Configuration](#configuration)
- [Startup verification](#startup-verification)
- [Storage operations](#storage-operations)
- [Observability and repair](#observability-and-repair)

<!-- section: boundary -->
## Runtime boundary

The Glue image builds `pysqlite3` separately for each OCI architecture from the SHA-verified
official SQLite amalgamation pinned in `config/runtime/sqlite-runtime.json`. It installs that private
DB-API module only in `/opt/mystack/venv`; it does not replace the AWS Glue base image's global
SQLite library. The generated runtime manifest records the SQLite version, architecture, and source
digests.

WAL is the default. SQLite documents a corruption race in versions through 3.51.2 when concurrent
connections write or checkpoint a WAL database; Mystack requires 3.51.3 or later and rejects an
unsafe runtime before Glue initializes its catalog.

The verified DB-API runtime backs Mystack's only durable Glue catalog. After verification succeeds,
the Glue application initializes a normalized SQLite schema in `glue.sqlite.database_file`. Immutable
Glue request documents remain canonical JSON `TEXT` where that preserves unmodeled fields; database,
table, archived-version, partition, optimizer, and optimizer-run identities are relational rows with
foreign keys. This keeps database/table rename local to parent rows and makes delete cascades atomic.

There is no JSON catalog fallback or migration path. A deployment that previously kept
`glue.state_file` must start with the configured SQLite catalog file; Mystack never silently imports,
uses, or overwrites a legacy JSON state document.

<!-- section: configuration -->
## Configuration

`glue.sqlite` is part of `config/runtime/mystack.yaml`. Relative `database_file` paths resolve below
`glue.data_root`; a relative driver manifest path resolves beside the mounted YAML file.

```yaml
glue:
  sqlite:
    database_file: catalog.sqlite3
    driver:
      module: pysqlite3.dbapi2
      expected_version: "3.53.4"
      minimum_wal_version: "3.51.3"
      manifest_file: /opt/mystack/sqlite-runtime/runtime-manifest.json
    journal_mode: wal
    synchronous: normal
    busy_timeout_milliseconds: 5000
    retry_limit: 3
    checkpoint:
      mode: passive
      auto_checkpoint_pages: 1000
```

`database_file` is the durable catalog database. Mount its **parent directory** writable: WAL creates
the durable `catalog.sqlite3-wal` and `catalog.sqlite3-shm` siblings beside it. `journal_mode` accepts
`wal` or `rollback`; `rollback` maps to SQLite's explicit `DELETE` journal mode and is never selected
automatically. `synchronous` accepts `off`, `normal`, `full`, or `extra`. `busy_timeout_milliseconds`
sets the DB-API wait bound and `retry_limit` adds bounded application retries for a contended writer.
`checkpoint.mode` accepts `passive`, `full`, `restart`, or `truncate`; `auto_checkpoint_pages` applies
SQLite's automatic WAL checkpoint threshold.

<!-- section: verification -->
## Startup verification

Before catalog initialization, the Glue process checks the selected driver module, reported SQLite
version, WAL build manifest, writable database directory, foreign keys, `busy_timeout`,
`synchronous`, selected journal mode, and WAL sibling-file creation. A WAL request whose driver,
version, manifest, or PRAGMA result does not match fails startup. Mystack does not silently change
the journal mode.

Run the same check without starting HTTP:

```bash
mystack-glue --config /etc/mystack/mystack.yaml --verify-sqlite-runtime
```

The command emits one JSON document containing the driver module, SQLite version, selected journal
mode, and verified PRAGMAs. The Glue image release preflight runs it for both `linux/amd64` and
`linux/arm64` images.

<!-- section: operations -->
## Storage operations

Mount a writable whole directory, not only `catalog.sqlite3`. The startup verifier creates and
removes an isolated probe there before schema initialization; the catalog then retains its database,
`-wal`, and `-shm` siblings in that same directory. All processes accessing one WAL database must run
on the same host and use the same mounted directory. Network filesystems are not a supported WAL
deployment.

Each catalog mutation starts a short `BEGIN IMMEDIATE` transaction, makes application-owned domain
decisions, conditionally updates the normalized rows, increments a diagnostic catalog revision, and
commits. SQLite permits one writer; readers use separate short-lived connections. A busy writer
waits for `busy_timeout_milliseconds`, then retries at most `retry_limit` times before the request
fails without committing a partial change. The adapter shields an in-flight commit from task
cancellation, then reports whether it committed or rolled back.

For a filesystem-level backup, stop every Glue process using the database, then copy the complete
directory. For an online backup, use SQLite's backup API. When a maintenance checkpoint is needed,
run the configured checkpoint mode and confirm it did not report `SQLITE_BUSY` before copying files.
Do not copy a live database file while separating it from its `-wal` sibling.

The intentional rollback escape hatch is a mounted configuration change followed by a Glue restart:

```yaml
glue:
  sqlite:
    journal_mode: rollback
    driver:
      module: sqlite3
```

This choice is visible as `manifest_verified: false` in runtime verification output. It is suitable
only when the operator deliberately accepts rollback-journal concurrency characteristics; it is not
a recovery path selected by Mystack.

<!-- section: observability -->
## Observability and repair

`glue.sqlite.runtime.verify.before`, `.after`, and `.failed` log the selected driver module, journal
mode, SQLite version, timeout, checkpoint policy, and a repair hint. `glue.sqlite_catalog.schema.*`
and `glue.sqlite_catalog.transaction.*` additionally log schema startup, bounded busy retries,
commit/rollback, duration, and a resource fingerprint. They do not log source URLs, credentials,
database contents, or request payloads. The health endpoint exposes the verified runtime document at
`/_mystack/health` under `sqlite_runtime`.

When a new base image or Python runtime breaks this boundary, inspect in this order:

1. `config/runtime/sqlite-runtime.json` for source version, URL shape, and checksums.
2. `glue/scripts/build_sqlite_driver.py` for verification, extraction, and extension compilation.
3. `glue/scripts/install_python_build_dependencies.py` for active-Python ABI header selection.
4. `glue/Dockerfile` for the private virtualenv installation boundary.
5. `glue/src/mystack/glue/adapters/outbound/sqlite_runtime.py` for startup capability checks.
6. `glue/src/mystack/glue/adapters/outbound/sqlite_catalog/` for schema, mapping, connection, and
   transaction behavior.
7. `config/runtime/mystack.yaml` and `glue/src/mystack/glue/config.py` for mounted policy parsing.

<!-- section: sources -->
## Official sources

- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
- [SQLite download and checksum format](https://www.sqlite.org/download.html)
- [AWS Glue local Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [pysqlite3 source build logic](https://github.com/coleifer/pysqlite3/blob/master/setup.py)
