<!-- doc-id: protocols/glue-sqlite-runtime -->
<!-- lang: en -->

[한국어](glue-sqlite-runtime.ko.md) | [English](glue-sqlite-runtime.md)

# Glue SQLite runtime contract

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
official SQLite amalgamation pinned in `config/sqlite-runtime.json`. It installs that private
DB-API module only in `/opt/mystack/venv`; it does not replace the AWS Glue base image's global
SQLite library. The generated runtime manifest records the SQLite version, architecture, and source
digests.

WAL is the default. SQLite documents a corruption race in versions through 3.51.2 when concurrent
connections write or checkpoint a WAL database; Mystack requires 3.51.3 or later and rejects an
unsafe runtime before Glue initializes its catalog.

<!-- section: configuration -->
## Configuration

`glue.sqlite` is part of `config/mystack.yaml`. Relative `database_file` paths resolve below
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

`journal_mode` accepts `wal` or `rollback`. `rollback` maps to SQLite's explicit `DELETE` journal
mode; it is never selected as an automatic fallback. `synchronous` accepts `off`, `normal`, `full`,
or `extra`. `checkpoint.mode` accepts `passive`, `full`, `restart`, or `truncate`; the later SQLite
catalog adapter will use this policy for its controlled checkpoints. `retry_limit` is reserved for
the same adapter's bounded `SQLITE_BUSY` retry loop.

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

For WAL, mount or retain the whole database directory, not only `catalog.sqlite3`. SQLite uses
`catalog.sqlite3-wal` and `catalog.sqlite3-shm` beside the database. All Glue processes that access
one WAL database must run on the same host and use the same mounted directory; network filesystems
are not a supported WAL deployment.

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
mode, SQLite version, timeout, checkpoint policy, and a repair hint. They do not log source URLs,
credentials, database contents, or request payloads. The health endpoint exposes the verified
runtime document at `/_mystack/health` under `sqlite_runtime`.

When a new base image or Python runtime breaks this boundary, inspect in this order:

1. `config/sqlite-runtime.json` for source version, URL shape, and checksums.
2. `glue/scripts/build_sqlite_driver.py` for verification, extraction, and extension compilation.
3. `glue/Dockerfile` for the private virtualenv installation boundary.
4. `glue/src/mystack/glue/adapters/outbound/sqlite_runtime.py` for startup capability checks.
5. `config/mystack.yaml` and `glue/src/mystack/glue/config.py` for mounted policy parsing.

<!-- section: sources -->
## Official sources

- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
- [SQLite download and checksum format](https://www.sqlite.org/download.html)
- [AWS Glue local Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [pysqlite3 source build logic](https://github.com/coleifer/pysqlite3/blob/master/setup.py)
