<!-- doc-id: protocols/glue-database-table-errors -->
<!-- lang: en -->

[한국어](glue-database-table-errors.ko.md) | [English](glue-database-table-errors.md)

# Glue database, table, and version error semantics

<!-- toc:start -->
## Contents

- [Supported decisions](#supported-decisions)
- [Archive, rename, and delete state](#archive-rename-and-delete-state)
- [System failures and concurrency](#system-failures-and-concurrency)
- [Explicit exclusions](#explicit-exclusions)
- [Verification and maintenance](#verification-and-maintenance)
- [Official sources](#official-sources)
<!-- toc:end -->

Mystack implements deterministic local-catalog decisions for the 13 database, table, table-version,
and import-status operations listed below. The pinned botocore model validates the public request
shape first. Application values are then validated before catalog lookup wherever they do not
depend on stored schema. This is an internal deterministic order based on public documentation; no
live AWS account is queried.

<!-- section: decisions -->
## Supported decisions

| Operation | Deterministic natural decision order after modeled validation |
| --- | --- |
| `CreateDatabase` | candidate name → duplicate database → durable save |
| `GetDatabase` | name → database existence |
| `GetDatabases` | `AttributesToGet`/token/page size → result page |
| `UpdateDatabase` | source/candidate names → source existence → destination conflict → durable save |
| `DeleteDatabase` | name → database existence → atomic catalog cascade → durable save |
| `CreateTable` | database/candidate names → database existence → duplicate table → durable save |
| `GetTable` | database/table names → table existence |
| `GetTables` | projection/expression/token/page size → database existence → result page |
| `UpdateTable` | source/candidate names and numeric `VersionId` → source existence → rename conflict → stale version → archive/mutation → durable save |
| `DeleteTable` | database/table names → table existence → atomic partition cascade → durable save |
| `GetTableVersion` | names and numeric version ID → table existence → version existence |
| `GetTableVersions` | names/token/page size → table existence → result page |
| `GetCatalogImportStatus` | success, or configured timeout/internal failure |

An invalid request or failed candidate never changes visible or durable state. Duplicate creates and
rename destinations use `AlreadyExistsException`; absent catalog resources use
`EntityNotFoundException`; application validation uses `InvalidInputException`. A stale
`UpdateTable.VersionId` uses `ConcurrentModificationException`, which is modeled by the official
`UpdateTable` operation. `VersionMismatchException` is a global Glue exception but is not an
`UpdateTable` modeled error, so Mystack does not expose it for this operation.

<!-- section: state -->
## Archive, rename, and delete state

Tables begin at version `0`. By default, `UpdateTable` archives the previous current version and
increments the version ID. `SkipArchive=true` still increments the ID but does not add the replaced
version to history. Database rename moves its tables, table versions, and partitions atomically;
table rename moves its partitions atomically. A rename collision is evaluated before a stale
version condition. Delete makes the database/table and its child resources inaccessible in one
local durable commit, matching the documented post-delete visibility while not emulating AWS's
asynchronous orphan cleanup implementation.

`GetDatabases.AttributesToGet` accepts `NAME` or `NAME,TARGET_DATABASE`; `GetTables.AttributesToGet`
accepts `NAME` or `NAME,TABLE_TYPE`. Supplying the field with an empty list or without `NAME` is an
`InvalidInputException`. Pagination tokens are opaque Mystack tokens and malformed tokens fail
before resource lookup.

<!-- section: system -->
## System failures and concurrency

A persistence `OSError` becomes a sanitized `InternalServiceException`/HTTP 500 only after the
repository has kept the candidate invisible and durable state unchanged. YAML fault rules reproduce
documented `OperationTimeoutException` or `InternalServiceException` before application/repository
access. Parallel writes are serialized; two writers using the same explicit version yield one
success and one `ConcurrentModificationException`. Writes without `VersionId` serialize and each
advance the authoritative version.

<!-- section: exclusions -->
## Explicit exclusions

Federation, encryption, Lake Formation transactions/audit context, resource-link access,
cross-account/cross-Region behavior, and authentication/authorization have no local trigger and are
outside scope. `ResourceNumberLimitExceededException` has no natural trigger because this release
does not define artificial catalog quotas. `ResourceNotReadyException` is not synthesized because
the supported catalog mutations have no asynchronous local resource state. Configured system faults
cover only timeout/internal errors; they never impersonate those excluded states.

<!-- section: verification -->
## Verification and maintenance

`glue/tests/test_database_table_error_semantics.py` runs parameterized AWS JSON boundary contracts
and snapshots the durable store before and after every failed operation. It also verifies projection,
archive, rename, cascade, and persistence rollback. Run only this bounded suite locally with the
configured timeout; public Proxy/boto3 coverage remains CI-owned. Update the inbound operation family
for shape/projection drift, the application aggregate for decision-order drift, and
`contracts/glue-error-conditions.yaml` for wire-code drift.

<!-- section: sources -->
## Official sources

- [AWS Glue database API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-databases.html)
- [AWS Glue table API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-tables.html)
- [UpdateTable](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [GetTableVersion](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersion.html)
- [DeleteDatabase](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteDatabase.html)
- [DeleteTable](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html)
- [botocore Glue model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
