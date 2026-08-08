<!-- doc-id: protocols/glue-open-table-format -->
<!-- lang: en -->

[한국어](glue-open-table-format.ko.md) | [English](glue-open-table-format.md)

# Glue Open Table Format input contract

This contract defines the supported `CreateTable.OpenTableFormatInput` and
`UpdateTable.UpdateOpenTableFormatInput` paths. The wire shape comes from the official AWS Glue
[`CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html),
[`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html), and pinned
botocore 1.43.66 model. Mystack does not query a live AWS account.

<!-- section: responsibility -->
## Responsibility boundary

The normal Iceberg GlueCatalog path receives a metadata pointer already written by Apache Iceberg;
Mystack stores that pointer losslessly. Open Table Format input is different: AWS defines schema,
partition, sort, location, and property documents that the catalog service must materialize.
Mystack therefore validates those inputs and writes the initial or revised Iceberg v2 metadata JSON.
Apache Iceberg still owns data files, manifests, snapshots, DML, retries, and later client commits.
The metadata layout follows the Apache Iceberg
[table metadata specification](https://iceberg.apache.org/spec/#table-metadata), not a private format.

The dependency direction is fixed:

```text
AWS JSON inbound mapper
  -> OpenTableFormatCommands
     -> IcebergOpenTableFormatPlanner (domain)
     -> IcebergMetadataStore port
        -> LocalStack-compatible S3 adapter
     -> existing TableCommands
```

The domain never imports boto3, S3, FastAPI, or a repository implementation. The S3 adapter never
reaches into catalog state.

<!-- section: create -->
## Create protocol

`CreateTable` accepts exactly one of `TableInput` and `OpenTableFormatInput`. The Open Table Format
path requires top-level `Name`, `IcebergInput.MetadataOperation=CREATE`, version `2` (including the
documented default), and `CreateIcebergTableInput.Location` plus `Schema`.

The deterministic order is:

1. Validate and normalize the complete Iceberg input without side effects.
2. Require the parent database and reject a duplicate normalized table name.
3. Write a uniquely named `00000-<id>.metadata.json` candidate to configured S3.
4. Publish a Glue `EXTERNAL_TABLE` with `table_type=ICEBERG` and `metadata_location`.
5. If catalog publication fails, delete only that unique unreferenced candidate as compensation.

The initial metadata includes the required Iceberg v2 UUID, location, schema/current schema,
partition specs/default spec, last field/partition IDs, sort orders/default order, properties,
empty snapshot/log/ref collections, and timestamps.

<!-- section: types -->
## Schema, partition, and sort support

The schema accepts all Iceberg primitives used by the v2 specification: boolean, int, long, float,
double, decimal, date, time, timestamp, timestamptz, string, UUID, fixed, and binary. Nested struct,
list, and map documents are recursive. Field, element, key, and value IDs must be globally unique;
identifier fields must exist, be required, and be primitive. Glue `StorageDescriptor.Columns` is a
derived Hive-compatible projection while the Iceberg JSON remains authoritative. Identifier fields
also reject float/double and optional-struct/list/map ancestry, and field IDs stay below Iceberg's
reserved metadata-column range, as required by the official
[identifier/reserved-ID rules](https://iceberg.apache.org/spec/#identifier-field-ids).

Partition specs support `identity`, `year`, `month`, `day`, `hour`, `void`, `bucket[N]`, and
`truncate[N]`; source IDs, field IDs, and names are validated. Write order supports those transforms,
ascending/descending direction, and both null orders. These forms follow the Iceberg
[partition transform](https://iceberg.apache.org/spec/#partition-transforms) and
[sort order](https://iceberg.apache.org/spec/#sorting-and-sort-orders) specifications.

<!-- section: update -->
## Update and concurrency protocol

`UpdateTable` accepts exactly one of `TableInput` and `UpdateOpenTableFormatInput`; the latter also
requires `Name` and an existing Iceberg metadata pointer. Mystack reads the current JSON, preserves
snapshots and unknown specification members, applies the requested transition, appends the previous
metadata entry, writes a unique next-version candidate, and atomically compares/swaps the Glue
`VersionId`. A stale writer receives `ConcurrentModificationException`, and its candidate is removed.

Supported `IcebergTableUpdate.Action` values are `add-schema`, `set-current-schema`, `add-spec`,
`set-default-spec`, `add-sort-order`, `set-default-sort-order`, `set-location`, `set-properties`, and
`remove-properties`. An omitted action replaces/upserts the supplied state members. Glue 5.0's local
Iceberg profile does not configure metadata encryption, so `add-encryption-key` and
`remove-encryption-key` deterministically return `InvalidInputException`.

S3 and catalog storage cannot form one distributed transaction. Mystack provides preflight,
unique candidate names, catalog CAS, and best-effort deletion; a failed compensation can leave an
unreferenced JSON object but never publishes a partial catalog definition.

<!-- section: errors -->
## Errors and evaluation order

Natural request/state failures reproduce the project-wide modeled codes: invalid schema/type/ID,
URI, transform, action, or mutually exclusive input becomes `InvalidInputException`; a missing
database/table becomes `EntityNotFoundException`; a duplicate table becomes
`AlreadyExistsException`; stale `VersionId` becomes `ConcurrentModificationException`; configured
S3/catalog persistence failure becomes `InternalServiceException`. The first failure in the
documented local order wins; no live-AWS ordering comparison is performed. Authentication,
authorization, IAM, Lake Formation, cross-account, and cross-Region errors are out of scope.

<!-- section: configuration-observability -->
## Configuration, logging, and repair locations

The Glue S3 adapter receives `localstack.endpoint_url`, region, credentials, and path-style setting
from `config/mystack.yaml`; no service/container name is hard-coded in the use case. Structured
`glue.open_table_format.*` and `glue.iceberg_metadata.*` events cover validation, read/write/delete,
publication, compensation, size, safe URI/document fingerprints, failure type, and `fix_hint`.
Metadata bodies and authorization values are never logged.

When a botocore, Glue, or Iceberg upgrade breaks this path, inspect in this order:

1. `glue/adapters/inbound/aws_table.py` for request member/nesting drift.
2. `glue/domain/open_table_format.py` for type, action, transform, or Iceberg spec drift.
3. `glue/application/open_table_format.py` for ordering, CAS, or compensation drift.
4. `glue/adapters/outbound/iceberg_metadata.py` for LocalStack/S3 codec or endpoint drift.
5. `glue/scripts/e2e/open_table_format.py` and `compatibility/cases.yaml` for real-client evidence.

<!-- section: evidence -->
## Verification evidence and limits

Fast tests cover nested types, global IDs, all layer boundaries, official boto3 serialization,
modeled errors, deterministic JSON, and failed-publication cleanup with explicit timeouts. The
existing single Glue 5 Spark E2E process creates through boto3 over the public Proxy, loads/appends
through Iceberg GlueCatalog, evolves through `UpdateOpenTableFormatInput`, reloads/appends, and then
checks Glue and LocalStack S3 metadata. This adds no second Spark startup.

The profile is Iceberg v2 only. Iceberg REST, PyIceberg, Flink, Trino, encryption-key management,
managed optimizers, authentication/authorization, Lake Formation, cross-account, and cross-Region
behavior are excluded.

<!-- section: sources -->
## Official sources

- [AWS Glue `OpenTableFormatInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html)
- [AWS Glue `CreateIcebergTableInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html)
- [AWS Glue `UpdateIcebergTableInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateIcebergTableInput.html)
- [AWS Glue `IcebergTableUpdate`](https://docs.aws.amazon.com/glue/latest/webapi/API_IcebergTableUpdate.html)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [Apache Iceberg metastore serialization](https://iceberg.apache.org/spec/#metastore-serialization)
