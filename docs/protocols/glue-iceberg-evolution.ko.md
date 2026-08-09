<!-- doc-id: protocols/glue-iceberg-evolution -->
<!-- lang: ko -->

[한국어](glue-iceberg-evolution.ko.md) | [English](glue-iceberg-evolution.md)

# GlueCatalog을 통한 Iceberg metadata evolution

<!-- toc:start -->
## 목차

- [책임 경계](#책임-경계)
- [보장하는 evolution profile](#보장하는-evolution-profile)
- [Glue wire 계약](#glue-wire-계약)
- [검증 근거](#검증-근거)
- [Logging과 수정 위치](#logging과-수정-위치)
- [한계](#한계)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 계약은 Glue 5.0 상호운용 profile에서 지원하는 Apache Iceberg 1.7.1 partition, schema, sort,
identifier evolution 동작을 고정합니다. 문법과 의미 규칙은 Iceberg 공식
[partitioning](https://iceberg.apache.org/docs/1.7.1/partitioning/),
[evolution](https://iceberg.apache.org/docs/1.7.1/evolution/),
[Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/) 문서를 기준으로 합니다.

<!-- section: responsibility -->
## 책임 경계

Spark와 Iceberg 1.7.1 runtime은 S3에 data file, manifest, snapshot, table metadata JSON,
partition spec, schema, sort order, identifier-field ID를 만듭니다. Mystack은 이 구조를 구현하거나
해석하지 않습니다. Iceberg가 보낸 `TableInput`을 보존하고 예상 `VersionId`와 함께 Glue
`Parameters.metadata_location` pointer를 원자적으로 바꿉니다. 자세한 내용은
[Iceberg GlueCatalog commit 계약](glue-iceberg-commits.ko.md)에 있습니다.

따라서 Iceberg partition field는 Glue Hive `PartitionKeys`나 Glue partition row가 되지 않습니다.
Hidden partitioning model에 따라 query는 source column을 filter하며 Iceberg가 물리 partition
layout을 caller에게 노출하지 않고 partition value를 유도하고 pruning합니다.

<!-- section: behavior -->
## 보장하는 evolution profile

고정된 Glue 5.0/Spark 3.5.4/Iceberg 1.7.1 profile은 table-driven 실제 runtime scenario 하나에서
다음 동작을 검증합니다.

| 영역 | 보장하는 형식 |
| --- | --- |
| Partition transform | identity, `bucket`, `truncate`, `year`, `month`, `day`, `hour` |
| Partition evolution | 과거 spec을 유지하면서 field add, drop, replace |
| Schema evolution | Top-level 및 nested field add/drop/rename |
| 안전한 widening | `int`에서 `long`, `float`에서 `double`, scale을 유지한 decimal precision 증가 |
| Sort order | 방향과 null order를 포함한 ordered, unordered, replacement order |
| Identifier field | Required field에 set, drop, 다시 set |
| Read 동작 | Evolution 전후에 쓴 row를 함께 읽고 source-column filter가 예상 결과를 반환 |

이 항목은 metadata-only Iceberg operation입니다. Partition spec이나 schema가 바뀌어도 기존 file을
다시 쓰지 않습니다. 이는 Iceberg가 문서화한 schema/partition evolution 동작이며 Glue emulator에
별도 구현한 로직이 아닙니다.

<!-- section: wire -->
## Glue wire 계약

각 Iceberg commit에서 AWS JSON 1.1 경계는 다음 `metadata_location`, 현재 Glue `VersionId`,
client가 만든 table definition을 담은 `UpdateTable`을 받습니다. Version이 맞으면 새 table version
하나를 공개하고 `SkipArchive=true`가 아니면 이전 definition을 archive합니다. Stale version은
`ConcurrentModificationException`을 반환하며 current table과 archive를 변경하지 않습니다.
`GetTable`과 `GetTableVersions`는 저장한 pointer와 client가 보낸 column/type 문자열을 모두 반환하고
가짜 partition key를 만들지 않습니다.

공식 request/response member는 AWS Glue
[`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html),
[`GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html),
[`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
계약을 따릅니다. Pointer가 가리키는 S3 JSON은 Iceberg
[table metadata specification](https://iceberg.apache.org/spec/#table-metadata)이 정의합니다.

<!-- section: evidence -->
## 검증 근거

빠른 `glue/tests/test_iceberg_evolution_catalog.py` 계약은 실제 AWS JSON 경계를 실행합니다.
Pointer, column, property를 손실 없이 versioning하는지, 가짜 Hive partition key가 없는지, archive
순서, stale-writer 오류 코드와 conflict 후 상태 무변경을 검증합니다.

CI 전용 `tests/e2e/test_glue_spark_catalog.py` scenario는 공식 Glue 5 image를 public Proxy와
LocalStack에 연결합니다. 위 표의 모든 형식을 실행하고 두 schema에서 쓴 row를 읽습니다. boto3로
최종 `metadata_location`을 얻은 뒤 S3 `GetObject`로 실제 metadata JSON을 내려받으며 JSON list
위치가 아니라 field ID로 관계를 해석합니다. 과거/현재 partition transform, 현재 schema와 nested
field, 안전하게 넓어진 type, identifier field, 전체 sort order를 검사합니다.

<!-- section: observability -->
## Logging과 수정 위치

`MYSTACK_E2E_SCENARIO`는 이름이 있는 각 DDL 경계의 안전한 before/after record를 출력합니다.
`glue.iceberg.commit.*`과 `glue.repository.*`는 table body나 S3 path를 기록하지 않고 version 판단과
저장 경계를 보여줍니다. Spark 또는 Iceberg를 올린 뒤 이 profile이 깨지면 다음을 확인합니다.

1. Spark DDL이나 runtime 동작 변화: `glue/scripts/e2e/iceberg_evolution.py`
2. Iceberg metadata spec 표현 변화: `test_support/iceberg_metadata.py`
3. Glue wire member 변화: `glue/adapters/inbound/aws_table.py`
4. Pointer/version 손실: `glue/application/table.py`, `glue/adapters/outbound/repository.py`
5. 고정 runtime, scenario, 검증 선언: `compatibility/cases.yaml`

<!-- section: limits -->
## 한계

Row-level write는 별도 [Iceberg row-level DML 계약](glue-iceberg-row-level-dml.ko.md)이 다룹니다.
Snapshot, reference, metadata table, procedure 동작은 [snapshot/reference/procedure
계약](glue-iceberg-snapshots-refs-procedures.ko.md)이 다룹니다. 이 evolution 계약은
rename/drop/purge를 [Iceberg lifecycle 계약](glue-iceberg-lifecycle.ko.md)에 위임합니다.
Open Table Format input은 별도 [입력 계약](glue-open-table-format.ko.md)에서 다룹니다. 인증, 인가,
IAM, Lake Formation, cross-account/cross-Region, PyIceberg, Flink, Trino는 계속 명시적인 프로젝트
제외 범위입니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue에서 Iceberg 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 partitioning](https://iceberg.apache.org/docs/1.7.1/partitioning/)
- [Apache Iceberg 1.7.1 evolution](https://iceberg.apache.org/docs/1.7.1/evolution/)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [Amazon S3 `GetObject`](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)
