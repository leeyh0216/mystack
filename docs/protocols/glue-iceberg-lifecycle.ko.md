<!-- doc-id: protocols/glue-iceberg-lifecycle -->
<!-- lang: ko -->

[한국어](glue-iceberg-lifecycle.ko.md) | [English](glue-iceberg-lifecycle.md)

# GlueCatalog을 통한 Iceberg rename, drop, purge

이 계약은 Glue 5.0, Spark 3.5.4, Iceberg 1.7.1의 table lifecycle 동작을 고정합니다.
Iceberg 공식 [Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)과 고정한
[`GlueCatalog` 구현](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416)을
따릅니다.

<!-- section: responsibility -->
## 책임 경계

Apache Iceberg가 SQL을 parse하고 rename과 purge를 여러 system에 걸친 operation으로 수행합니다.
Mystack은 Iceberg lifecycle algorithm을 다시 구현하지 않습니다. 개별 modeled Glue
[`GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html),
[`CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html),
[`DeleteTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html)을 제공합니다.
각 operation은 catalog state를 원자적으로 commit합니다. 추적 file 삭제는 Iceberg S3 FileIO가
담당하고 LocalStack은 설정한 object-store endpoint를 제공합니다.

<!-- section: rename -->
## Rename 순서와 보장

고정한 Iceberg 1.7.1은 target namespace를 확인하고 source를 읽은 뒤, 같은 metadata pointer와
location을 가진 destination Glue table을 만들고 source를 purge 없이 삭제합니다. Source 삭제가
실패하면 새 destination 삭제를 보상 작업으로 시도합니다. 이는 하나의 원자적 Glue request가 아니라
문서화한 호출 순서입니다.

실제 runtime scenario는 다음을 보장합니다.

| 경우 | 보장 결과 |
| --- | --- |
| 같은 namespace 안의 rename | Destination에서 row를 읽을 수 있고 S3 object가 유지됨 |
| Namespace 사이의 rename | Destination의 Glue version은 `0`; location과 `metadata_location`은 원래 Iceberg table을 계속 가리킴 |
| 같은 정규화 이름 또는 case-only target | Spark/Iceberg가 거부하며 두 번째 논리 table이 생기지 않음 |
| Source 또는 target namespace 없음 | 실패하고 destination을 공개하지 않음 |
| Destination이 이미 존재 | Glue 경계의 `AlreadyExistsException`을 유지하고 기존 두 table을 보존 |
| Source 삭제 persistence 실패 | HTTP 500 `InternalServiceException`; 실패한 삭제 state를 공개하지 않고 Iceberg 방식 보상 삭제가 destination만 제거 |

Mystack은 catalog identifier를 소문자로 정규화합니다. 빠른 계약은 `events`와 `EVENTS`가
persistence 전에 충돌하고 누락 read가 HTTP 400 `EntityNotFoundException`을 반환함을 증명합니다.
오류는 Mystack 내부의 결정적 validation 및 operation 순서로 평가하며 실제 AWS 계정과 비교하지
않습니다.

<!-- section: drop -->
## Drop과 purge 순서

Iceberg 1.7.1은 Spark DDL 문서와 같이 두 형식을 구분합니다.

- `DROP TABLE`: Glue `DeleteTable`만 호출하며 table data와 metadata object를 유지합니다.
- `DROP TABLE ... PURGE`: current Iceberg metadata를 읽고 Glue `DeleteTable`을 먼저 호출한 뒤
  `CatalogUtil.dropTableData`로 해당 metadata가 추적하는 file을 삭제합니다.

E2E scenario는 추적 data/metadata와 함께 각 table prefix 안에 추적하지 않는 sentinel을
작성합니다. 일반 drop은 모든 object를 보존합니다. Purge는 추적한 Iceberg object를 삭제하지만
추적하지 않는 sentinel과 별도의 unrelated object를 보존합니다. 이 증거는 Mystack이 위험한 재귀
prefix 삭제를 구현하지 않았음을 보여줍니다. `IF EXISTS` retry는 Spark/Iceberg가 받아들이며 catalog
state를 다시 만들지 않습니다.

<!-- section: failure -->
## 실패와 복구 경계

Rename 보상은 여러 Glue 호출 사이의 best effort이며, 각 Mystack 호출은 원자적 catalog
transaction입니다. Source `DeleteTable` 실패 시 Iceberg 보상 삭제가 destination을 제거할 때까지
source와 destination이 모두 보입니다. Source는 일부만 삭제되는 상태가 되지 않습니다.

Purge는 의도적으로 Glue와 S3 전체에서 transactional하지 않습니다. 고정한 구현은 Glue entry를
추적 S3 file보다 먼저 삭제합니다. 이후 S3 삭제가 실패하면 SQL `IF EXISTS` retry는 사라진 catalog
pointer를 다시 읽을 수 없습니다. 따라서 이전에 확보한 metadata location 또는 별도로 제어하는
orphan-file cleanup으로 복구해야 합니다. Mystack은 Iceberg보다 강한 원자성을 주장하지 않습니다.

<!-- section: evidence -->
## 검증 근거

`glue/tests/test_iceberg_lifecycle_catalog.py`가 Spark 없이 modeled error, pointer copy, 원자적 delete,
보상 순서를 고정합니다. `glue/scripts/e2e/iceberg_lifecycle.py`는 Glue image에서 실제 Iceberg SQL을
실행합니다. `tests/e2e/test_glue_spark_catalog.py`는 public Proxy와 S3 endpoint를 통해 결과 Glue
definition을 boto3로 확인하고 object 존재 여부를 검증합니다. Spark process와 test 모두 설정한
E2E timeout을 사용합니다.

<!-- section: observability -->
## Logging과 수정 위치

Scenario의 모든 SQL과 S3 side effect는 전, 후 또는 안전한 exception type과 함께
`MYSTACK_E2E_SCENARIO`를 출력합니다. `glue.repository.transaction.*`,
`glue.repository.persistence.*` event는 table document나 object 내용을 노출하지 않으면서 operation,
resource fingerprint, side-effect phase, rollback, 수정 hint를 식별합니다.

Upgrade 후 이 profile이 깨지면 다음을 확인합니다.

1. Spark SQL 또는 결과 변화: `glue/scripts/e2e/iceberg_lifecycle.py`
2. 호출 순서 변화: Iceberg `GlueCatalog.renameTable`, `dropTable`
3. Modeled request member 변화: `glue/adapters/inbound/aws_table.py`
4. 원자성 회귀: `glue/application/table.py`, `glue/adapters/outbound/repository.py`
5. 고정 runtime과 capability 근거: `compatibility/cases.yaml`

<!-- section: limits -->
## 한계

이 profile은 Glue와 S3 전체의 rename/purge 원자성, 예약 optimizer service, catalog 삭제 이후 S3
삭제 실패의 자동 복구를 보장하지 않습니다. 인증, 인가, IAM, Lake Formation,
cross-account/cross-Region, PyIceberg, Flink, Trino는 제외합니다. Open Table Format input은 별도
[입력 계약](glue-open-table-format.ko.md)에서 다룹니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue `GetTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTable.html)
- [AWS Glue `CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html)
- [AWS Glue `DeleteTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html)
- [Apache Iceberg 1.7.1 Spark DDL](https://iceberg.apache.org/docs/1.7.1/spark-ddl/)
- [Apache Iceberg 1.7.1 `GlueCatalog`](https://github.com/apache/iceberg/blob/apache-iceberg-1.7.1/aws/src/main/java/org/apache/iceberg/aws/glue/GlueCatalog.java#L311-L416)
