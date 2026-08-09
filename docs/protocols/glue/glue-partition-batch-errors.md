<!-- doc-id: protocols/glue/glue-partition-batch-errors -->
<!-- lang: en -->

[한국어](glue-partition-batch-errors.ko.md) | [English](glue-partition-batch-errors.md)

# Glue partition and batch error contract

<!-- toc:start -->
## Contents

- [Validation layers and first failure](#validation-layers-and-first-failure)
- [Single-operation decisions](#single-operation-decisions)
- [Update and Spark Hive rename](#update-and-spark-hive-rename)
- [Batch ordering and partial success](#batch-ordering-and-partial-success)
- [Logging, tests, and repair location](#logging-tests-and-repair-location)
- [Exclusions](#exclusions)
- [Official sources](#official-sources)
<!-- toc:end -->

This contract defines the deterministic behavior of Mystack's nine implemented partition
operations. It is based on the public AWS Glue API pages and the pinned botocore model; no test or
decision calls a live AWS account. The generated [Glue error matrix](../../compatibility/api-coverage.md)
remains the machine-readable operation inventory.

<!-- section: layers -->
## Validation layers and first failure

The first failing condition stops the request in this order:

1. The shared AWS JSON 1.1 boundary validates required members, JSON types, patterns, enums, and
   every modeled maximum string/list/map/numeric constraint.
2. Configured `OperationTimeoutException` or `InternalServiceException` injection runs before the
   application and repository.
3. Names, pagination tokens, segment bounds, and expression syntax are checked without mutation.
4. The parent table is resolved. Partition value count is then compared with its partition-key
   count.
5. The source partition and destination conflict are evaluated where the operation needs them.
6. Mutating batch entries execute sequentially in request order. Each successful entry is durably
   committed before the next entry starts.

This is Mystack's reviewed order where AWS does not publish precedence between multiple invalid
conditions. It does not claim an undocumented AWS order.

<!-- section: operations -->
## Single-operation decisions

| Operation | Application order after wire validation and injection |
| --- | --- |
| `CreatePartition` | parent table → value count → duplicate tuple → durable save |
| `GetPartition` | parent table → value count → partition lookup |
| `GetPartitions` | page token → segment → expression syntax → parent table → expression/schema binding → filter/segment/page |
| `UpdatePartition` | parent table → old-value count → source partition → new-value count → destination conflict → durable save |
| `DeletePartition` | parent table → value count → partition lookup → durable save |

A duplicate create returns `AlreadyExistsException`. Missing parents or source partitions return
`EntityNotFoundException`. Bad cardinality, token, segment, expression, or update destination returns
`InvalidInputException`. A failed condition does not publish its candidate state.

<!-- section: update -->
## Update and Spark Hive rename

The public [`UpdatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdatePartition.html)
page says `PartitionInput.Values` cannot change. However, the AWS-maintained Glue Hive client
implements `renamePartition` by passing the old `PartitionValueList` and the new partition values to
`UpdatePartition` ([pinned client source](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/53d09f0c97edb913b02e00904b6620ea7468e8f5/aws-glue-datacatalog-spark-client/src/main/java/com/amazonaws/glue/catalog/metastore/AWSCatalogMetastoreClient.java#L1351-L1385),
[delegate source](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/53d09f0c97edb913b02e00904b6620ea7468e8f5/aws-glue-datacatalog-client-common/src/main/java/com/amazonaws/glue/catalog/metastore/GlueMetastoreClientDelegate.java#L1814-L1822)).

Mystack therefore supports that officially maintained Spark/Hive rename path. If `Values` is
omitted, the old tuple is preserved. If the new tuple already exists, Mystack returns the modeled
`InvalidInputException`; `UpdatePartition` does not declare `AlreadyExistsException` in the API page
or pinned botocore operation model. This explicit compatibility decision is covered by local
contracts and the CI-only Spark Hive DDL scenario.

<!-- section: batches -->
## Batch ordering and partial success

Every batch resolves its parent table before processing entries. A missing parent is an
operation-level `EntityNotFoundException`, never an item error or an empty success.

- `BatchCreatePartition` returns stable `PartitionError` entries for invalid or already-present
  items. A repeated tuple can succeed once and then fail as already present.
- `BatchUpdatePartition` and `BatchDeletePartition` return stable item `ErrorDetail` entries. A
  repeated source observes the result of the earlier entry.
- `BatchGetPartition` returns found partitions in request order, including repeated keys. Valid keys
  that are not returned appear in `UnprocessedKeys` in request order. Because this response has no
  item error field, a bad value count fails the whole operation with `InvalidInputException`.
- Item errors do not roll back earlier successful entries. A persistence failure returns the
  operation-level `InternalServiceException`: the failed candidate is rolled back, earlier durable
  entries remain, and later entries are not attempted.

The response structures follow the official [`BatchCreatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchCreatePartition.html),
[`BatchGetPartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchGetPartition.html),
[`BatchUpdatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchUpdatePartition.html),
and [`BatchDeletePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchDeletePartition.html)
pages.

<!-- section: maintenance -->
## Logging, tests, and repair location

`glue.partition_batch.before`, `.item.failed`, and `.after` record operation, item counts, safe item
index, failure type, and outcome counts without partition values. Expression parse, schema binding,
evaluation, and segment events use only a fingerprint, operator shape, types, and counts.

When a client upgrade breaks:

1. `protocol.validation.failed` points to the pinned model or generic validation in
   `shared/aws_protocol/model.py`.
2. `adapter.mapping_failure` points to `glue/adapters/inbound/aws_partition.py` or `aws_batch.py`.
3. Batch item/order drift points to `glue/application/batch.py`; value, update, or list order points
   to `glue/application/partition.py` and the immutable domain model.
4. `persistence.side_effect_failed` points to repository transaction before/after/rollback events.

The fast contract is `glue/tests/test_partition_batch_error_semantics.py`. Public Proxy boto3,
Spark Hive, and AWS SDK for pandas paths remain CI-owned and use explicit timeouts.

<!-- section: exclusions -->
## Exclusions

Authentication, authorization, IAM, Lake Formation, cross-account/cross-Region behavior, live-AWS
comparison, Glue Jobs, and Crawlers are outside this contract.

<!-- section: sources -->
## Official sources

- [AWS Glue partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [AWS Glue exceptions](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)
- [AWS Glue `GetPartitions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [botocore Glue service model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
- [AWS Glue Data Catalog client for Apache Hive Metastore](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore)
