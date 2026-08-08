<!-- doc-id: protocols/glue-iceberg-snapshots-refs-procedures -->
<!-- lang: ko -->

[한국어](glue-iceberg-snapshots-refs-procedures.ko.md) | [English](glue-iceberg-snapshots-refs-procedures.md)

# GlueCatalog을 통한 Iceberg snapshot, reference, procedure

이 계약은 Glue 5.0, Spark 3.5.4, Iceberg 1.7.1의 snapshot 탐색과 maintenance surface를
고정합니다. SQL 동작은 Iceberg 공식
[query](https://iceberg.apache.org/docs/1.7.1/spark-queries/),
[DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/),
[procedure](https://iceberg.apache.org/docs/1.7.1/spark-procedures/) 문서를 따릅니다.

<!-- section: responsibility -->
## 책임 경계

Apache Iceberg가 time travel, reference DDL, metadata-table query, snapshot 관리, compaction,
expiration, orphan cleanup을 parse하고 실행합니다. S3 FileIO를 통해 metadata와 data object도
작성합니다. Mystack은 이 알고리즘을 다시 구현하지 않으며 commit 중 snapshot JSON을 해석하지도
않습니다. Client가 만든 Glue `TableInput`을 손실 없이 저장하고 예상 `VersionId`로
`metadata_location`을 원자적으로 전진시킵니다. LocalStack은 설정한 S3 endpoint를 제공합니다.

<!-- section: behavior -->
## 보장하는 profile

고정한 실제 runtime scenario는 다음을 보장합니다.

| 영역 | 근거 |
| --- | --- |
| Time travel | `VERSION AS OF`, `TIMESTAMP AS OF`가 첫 snapshot의 정확한 row 반환 |
| Reference | 특정 snapshot의 branch/tag 생성, branch append, main 격리, branch/tag read |
| Metadata table | `history`, `snapshots`, `files`, `manifests`, `partitions` query가 비어 있지 않음 |
| Snapshot procedure | `rollback_to_snapshot`, `set_current_snapshot`, append `cherrypick_snapshot`이 예상 snapshot ID를 반환하고 공개 |
| Maintenance | `rewrite_data_files`가 작은 file을 두 개 이상 rewrite하고 `rewrite_manifests`가 row 변경 없이 manifest rewrite |
| Expiration | Reference가 사라진 branch snapshot을 명시적으로 만료하고 current row 유지 |
| Orphan cleanup | 전용 과거 candidate가 dry-run에 나타나고 S3에 유지되며 실제 삭제 결과에 나타난 뒤 S3에서 사라짐 |

Snapshot 만료 전에 branch와 tag를 삭제합니다. Orphan cleanup에는 한 row짜리 `file_list_view`를
전달하므로 관련 없는 object를 나열하거나 대상으로 삼지 않습니다. 시험 table과 object prefix는
E2E 실행마다 고유합니다.

<!-- section: wire -->
## Glue wire와 원자성 계약

Table metadata를 바꾸는 reference DDL이나 procedure는 최종적으로 마지막 Glue `VersionId`와 함께
`UpdateTable`을 보냅니다. Version이 다르면 durable/visible state를 바꾸기 전에 HTTP 400
`ConcurrentModificationException`을 반환합니다. 빠른 계약은 정확한 version, stale rollback
candidate 이후 변경 없는 catalog, archive에 해당 metadata pointer가 없음을 증명합니다. 이는 AWS
Glue [`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html),
[`GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)를 따릅니다.

<!-- section: evidence -->
## 검증 근거

`glue/tests/test_iceberg_snapshot_ref_catalog.py`가 빠른 AWS JSON 1.1 pointer 계약입니다.
`glue/scripts/e2e/iceberg_snapshot_refs.py`는 `tests/e2e/test_glue_spark_catalog.py`가 public Proxy를
통해 호출하는 CI 전용 실제 Iceberg scenario입니다. Host test는 boto3로 최종 Glue pointer를 읽고
metadata JSON을 내려받아 `main`만 남았는지와 만료 snapshot 부재를 확인하며 orphan object가 S3
`404`/`NoSuchKey`인지 증명합니다. 모든 wait와 Spark process는 compatibility case에 설정한
timeout을 사용합니다.

<!-- section: observability -->
## Logging과 수정 위치

SQL/procedure/S3 side-effect 경계마다 `MYSTACK_E2E_SCENARIO`가 전, 후 또는 안전한 exception type만
포함해 출력됩니다. 기존 `glue.iceberg.commit.*`, `glue.repository.*` event는 SQL, table location,
payload를 기록하지 않고 catalog CAS와 persistence 경계를 보여줍니다.

Iceberg나 Spark upgrade 후 이 profile이 깨지면 다음을 확인합니다.

1. SQL, 결과 schema, procedure 변화: `glue/scripts/e2e/iceberg_snapshot_refs.py`
2. Iceberg metadata format 표현 변화: `test_support/iceberg_metadata.py`
3. Modeled Glue request member 변화: `glue/adapters/inbound/aws_table.py`
4. CAS 또는 archive 손실: `glue/application/table.py`, `glue/adapters/outbound/repository.py`
5. 고정 runtime과 capability 근거: `compatibility/cases.yaml`

<!-- section: limits -->
## 한계

Rename/drop/purge는 [Iceberg lifecycle 계약](glue-iceberg-lifecycle.ko.md)이 다룹니다.
이 계약은 예약 optimizer service, 모든 procedure option, 모든 metadata table을 보장하지 않습니다.
Open Table Format input은 별도 [입력 계약](glue-open-table-format.ko.md)에서 다룹니다. 인증, 인가,
IAM, Lake Formation, cross-account/cross-Region, PyIceberg, Flink, Trino는 명시적으로 제외합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue에서 Iceberg 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 Spark query](https://iceberg.apache.org/docs/1.7.1/spark-queries/)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg 1.7.1 Spark procedure](https://iceberg.apache.org/docs/1.7.1/spark-procedures/)
- [Apache Iceberg 1.7.1 branch와 tag](https://iceberg.apache.org/docs/1.7.1/branching/)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `GetTableVersions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
