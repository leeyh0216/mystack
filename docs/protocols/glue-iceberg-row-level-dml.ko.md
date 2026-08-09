<!-- doc-id: protocols/glue-iceberg-row-level-dml -->
<!-- lang: ko -->

[한국어](glue-iceberg-row-level-dml.ko.md) | [English](glue-iceberg-row-level-dml.md)

# GlueCatalog을 통한 Iceberg row-level DML

<!-- toc:start -->
## 목차

- [책임 경계](#책임-경계)
- [보장하는 profile](#보장하는-profile)
- [Glue wire와 실패 계약](#glue-wire와-실패-계약)
- [검증 근거](#검증-근거)
- [Logging과 수정 위치](#logging과-수정-위치)
- [한계](#한계)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 계약은 Glue 5.0, Spark 3.5.4, Iceberg 1.7.1 profile에서 지원하는 row-level write 동작을
고정합니다. Iceberg 공식 [Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/)와
[write-mode configuration](https://iceberg.apache.org/docs/1.7.1/configuration/) 계약을 따릅니다.

<!-- section: responsibility -->
## 책임 경계

Iceberg Spark extension은 `INSERT`, `UPDATE`, `DELETE`, `MERGE`를 plan하고 실행하며 data/delete
file, manifest, snapshot summary, table metadata를 S3에 만듭니다. Mystack은 SQL을 parse하거나 row를
평가하지 않고 copy-on-write와 merge-on-read도 구현하지 않습니다. Client가 만든 Glue
`TableInput`을 손실 없이 저장하고 예상 `VersionId`가 현재 값일 때 새 `metadata_location`을
원자적으로 commit합니다.

Pointer transaction은 기존 [Iceberg GlueCatalog commit 계약](glue-iceberg-commits.ko.md)을
사용합니다. S3 object와 snapshot 의미론은 Iceberg
[snapshot specification](https://iceberg.apache.org/spec/#snapshots)을 따릅니다.

<!-- section: behavior -->
## 보장하는 profile

고정한 실제 runtime scenario는 다음을 보장합니다.

| 영역 | 검증 근거 |
| --- | --- |
| Append | `INSERT INTO`가 기존 row를 유지하고 새 row를 추가 |
| Overwrite | Dynamic `INSERT OVERWRITE`가 표시된 identity partition만 교체하고 다른 partition을 보존 |
| Copy-on-write | `UPDATE`, `DELETE FROM`, matched/not-matched `MERGE INTO` action이 예상 row를 만들고 현재 delete file 수는 0 |
| Merge-on-read | 같은 row-level mutation 계열이 예상 row를 만들고 실제 Iceberg v2 delete-file 근거를 유지 |
| Merge validation | 한 target row와 일치하는 source row가 두 개이면 Iceberg Spark write 계약에 따라 실패 |
| 실패한 commit | 실패한 merge는 Glue version과 Iceberg snapshot을 만들지 않고 이전 row와 pointer를 current로 유지 |
| 경합 | 결정적인 stale-pointer 계약이 losing candidate를 거부하고 기존 두-container test가 같은 Glue CAS 경로의 Iceberg refresh/retry를 검증 |

`write.delete.mode`, `write.update.mode`, `write.merge.mode`를 `copy-on-write` 또는
`merge-on-read`로 명시합니다. Client의 암묵적 기본값은 검증 근거로 사용하지 않습니다.
Merge-on-read delete file은 v2 기능이므로 table format version은 2입니다.

<!-- section: wire -->
## Glue wire와 실패 계약

성공한 각 row-level Iceberg commit은 이전 `VersionId`와 다음 metadata pointer를 담은 modeled Glue
`UpdateTable` 하나를 보냅니다. Scenario에서 COW는 성공 snapshot/Glue pointer 변경이 6개이고 MOR은
4개입니다. 최종 Glue version과 Iceberg snapshot 수가 정확히 같으므로 예상한 invalid merge가 추가
candidate를 공개하지 않았음을 확인할 수 있습니다.

Stale `UpdateTable`은 persistence 전에 HTTP 400 `ConcurrentModificationException`을 반환합니다.
Current pointer, archive, 저장한 table property는 바뀌지 않습니다. Member와 response code는 AWS Glue
[`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html),
[`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)를
따릅니다. Glue commit 성공 이후의 row/file 의미론은 계속 Iceberg가 소유합니다.

<!-- section: evidence -->
## 검증 근거

빠른 `glue/tests/test_iceberg_row_level_catalog.py` 계약은 AWS JSON 1.1 경계를 실행합니다. MOR
pointer 하나를 commit한 뒤 stale delete candidate를 보내고 modeled error, durable state 무변경,
정확한 current pointer, 모든 table version에서 losing metadata location이 없음을 확인합니다.

CI 전용 `tests/e2e/test_glue_spark_catalog.py` scenario는 공식 Glue 5 image에서 public Proxy와
LocalStack을 사용합니다. 중요 경계 이후 row를 확인하고 boto3로 최종 pointer를 읽은 뒤 S3에서 실제
table metadata JSON을 내려받습니다. Format version, write-mode property, snapshot 수, current snapshot,
전체 delete-file 근거를 검증합니다. 모든 process/test wait는 compatibility case의 명시적 timeout
안에서 실행합니다.

<!-- section: observability -->
## Logging과 수정 위치

각 DML 경계는 `MYSTACK_E2E_SCENARIO`로 scenario 이름, phase, 안전한 exception class만 출력합니다.
기존 `glue.iceberg.commit.*`, `glue.repository.*` event는 SQL body나 S3 path 대신 fingerprint를
사용해 pointer 판단과 persistence lifecycle을 보여줍니다.

Client를 올린 뒤 이 profile이 깨지면 다음을 확인합니다.

1. Spark SQL 또는 Iceberg write-mode 변화: `glue/scripts/e2e/iceberg_row_level.py`
2. Iceberg snapshot-summary 표현 변화: `test_support/iceberg_metadata.py`
3. Glue request member 변화: `glue/adapters/inbound/aws_table.py`
4. CAS/version 손실: `glue/application/table.py`,
   `glue/adapters/outbound/sqlite_catalog/repository.py`
5. 고정 profile과 scenario 변경: typed pytest compatibility annotation

<!-- section: limits -->
## 한계

Snapshot time travel, branch/tag write, metadata table, procedure는
[snapshot/reference/procedure 계약](glue-iceberg-snapshots-refs-procedures.ko.md)이 다룹니다. 이
row-level 계약은 rename/drop/purge를 [Iceberg lifecycle 계약](glue-iceberg-lifecycle.ko.md)에
위임합니다. Open Table Format input은 별도 [입력 계약](glue-open-table-format.ko.md)에서 다룹니다.
인증, 인가, IAM, Lake Formation, cross-account/cross-Region, PyIceberg, Flink, Trino도 제외합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue에서 Iceberg 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 Spark writes](https://iceberg.apache.org/docs/1.7.1/spark-writes/)
- [Apache Iceberg 1.7.1 configuration](https://iceberg.apache.org/docs/1.7.1/configuration/)
- [Apache Iceberg snapshot specification](https://iceberg.apache.org/spec/#snapshots)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
