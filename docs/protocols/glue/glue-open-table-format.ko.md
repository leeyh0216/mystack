<!-- doc-id: protocols/glue/glue-open-table-format -->
<!-- lang: ko -->

[한국어](glue-open-table-format.ko.md) | [English](glue-open-table-format.md)

# Glue Open Table Format 입력 계약

<!-- toc:start -->
## 목차

- [책임 경계](#책임-경계)
- [Create protocol](#create-protocol)
- [Schema, partition, sort 지원](#schema-partition-sort-지원)
- [Update와 동시성 protocol](#update와-동시성-protocol)
- [오류와 평가 순서](#오류와-평가-순서)
- [설정, logging, 수정 위치](#설정-logging-수정-위치)
- [검증 근거와 한계](#검증-근거와-한계)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 계약은 지원하는 `CreateTable.OpenTableFormatInput`과
`UpdateTable.UpdateOpenTableFormatInput` 경로를 정의합니다. Wire 구조는 AWS Glue 공식
[`CreateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateTable.html),
[`UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html), 고정한 botocore
1.43.66 모델을 기준으로 합니다. Mystack은 실제 AWS 계정을 조회하지 않습니다.

<!-- section: responsibility -->
## 책임 경계

일반 Iceberg GlueCatalog 경로에서는 Apache Iceberg가 이미 작성한 메타데이터 pointer를 받아 Mystack이
무손실로 저장합니다. Open Table Format 입력은 다릅니다. AWS가 카탈로그 서비스에서 materialize할
schema, partition, sort, location, property document를 정의하므로 Mystack이 이를 검증하고 최초 또는
변경된 Iceberg v2 메타데이터 JSON을 작성합니다. Data 파일, manifest, snapshot, DML, retry와 이후 클라이언트
commit은 계속 Apache Iceberg가 소유합니다. Metadata layout은 private format이 아니라 Apache Iceberg
[table metadata specification](https://iceberg.apache.org/spec/#table-metadata)을 따릅니다.

의존 방향은 다음으로 고정합니다.

```text
AWS JSON inbound mapper
  -> OpenTableFormatCommands
     -> IcebergOpenTableFormatPlanner (domain)
     -> IcebergMetadataStore port
        -> LocalStack 호환 S3 adapter
     -> 기존 TableCommands
```

Domain은 boto3, S3, FastAPI, repository 구현을 import하지 않습니다. S3 어댑터는 카탈로그 state에
접근하지 않습니다.

<!-- section: create -->
## Create protocol

`CreateTable`은 `TableInput`과 `OpenTableFormatInput` 중 정확히 하나만 받습니다. Open Table Format
경로에는 top-level `Name`, `IcebergInput.MetadataOperation=CREATE`, 문서상 default를 포함한 version
`2`, `CreateIcebergTableInput.Location`, `Schema`가 필요합니다.

결정적 실행 순서는 다음과 같습니다.

1. Side effect 없이 Iceberg 입력 전체를 검증·정규화합니다.
2. Parent database 존재와 정규화한 table name 중복을 확인합니다.
3. 설정한 S3에 고유한 `00000-<id>.metadata.json` candidate를 씁니다.
4. `table_type=ICEBERG`, `metadata_location`을 가진 Glue `EXTERNAL_TABLE`을 공개합니다.
5. Catalog 공개 실패 시 해당 고유 미참조 candidate만 보상 삭제합니다.

최초 메타데이터에는 Iceberg v2 UUID, location, schema/current schema, partition specs/default spec,
마지막 field/partition ID, sort orders/default order, properties, 빈 snapshot/log/ref collection,
timestamp가 포함됩니다.

<!-- section: types -->
## Schema, partition, sort 지원

Schema는 v2 specification에서 사용하는 boolean, int, long, float, double, decimal, date, time,
timestamp, timestamptz, string, UUID, fixed, binary primitive를 지원합니다. Nested struct/list/map
document는 재귀적으로 처리합니다. Field, element, key, value ID는 전체 schema에서 고유해야 하고
identifier field는 존재하는 required primitive여야 합니다. Glue `StorageDescriptor.Columns`는
Hive 호환 projection이며 Iceberg JSON이 authoritative합니다. Identifier field는 float/double과
optional struct/list/map 아래 경로를 거부하고 field ID는 Iceberg 메타데이터 column 예약 범위보다
작아야 합니다. 이는 공식 [identifier/reserved-ID
규칙](https://iceberg.apache.org/spec/#identifier-field-ids)을 따릅니다.

Partition spec은 `identity`, `year`, `month`, `day`, `hour`, `void`, `bucket[N]`, `truncate[N]`을
지원하며 원본 ID, field ID, name을 검증합니다. Write order는 같은 transform, asc/desc, 두 null
order를 지원합니다. 이는 Iceberg [partition transform](https://iceberg.apache.org/spec/#partition-transforms),
[sort order](https://iceberg.apache.org/spec/#sorting-and-sort-orders) specification을 따릅니다.

<!-- section: update -->
## Update와 동시성 protocol

`UpdateTable`은 `TableInput`과 `UpdateOpenTableFormatInput` 중 정확히 하나만 받으며 후자에는 `Name`과
기존 Iceberg 메타데이터 pointer가 필요합니다. Mystack은 current JSON을 읽고 snapshot과 알지 못하는
spec member를 보존한 뒤 transition을 적용하고 previous 메타데이터 entry를 추가합니다. 고유한 다음
version candidate를 쓴 뒤 Glue `VersionId`를 원자적으로 compare/swap합니다. Stale writer에는
`ConcurrentModificationException`을 반환하고 candidate를 삭제합니다.

지원하는 `IcebergTableUpdate.Action`은 `add-schema`, `set-current-schema`, `add-spec`,
`set-default-spec`, `add-sort-order`, `set-default-sort-order`, `set-location`, `set-properties`,
`remove-properties`입니다. Action이 없으면 전달한 state member를 replace/upsert합니다. Glue 5.0 로컬
Iceberg 프로필은 메타데이터 encryption을 구성하지 않으므로 `add-encryption-key`와
`remove-encryption-key`는 결정적으로 `InvalidInputException`을 반환합니다.

S3와 카탈로그 storage는 하나의 distributed transaction을 만들 수 없습니다. Mystack은 preflight,
고유 candidate name, 카탈로그 CAS, best-effort 삭제를 제공합니다. 보상 삭제 실패는 미참조 JSON을
남길 수 있지만 일부만 적용된 카탈로그 definition은 공개하지 않습니다.

<!-- section: errors -->
## 오류와 평가 순서

자연스러운 request/state 실패는 project 공통 modeled code로 변환됩니다. 잘못된 schema/type/ID,
URI, transform, action, 상호 배타 input은 `InvalidInputException`, 없는 database/table은
`EntityNotFoundException`, 중복 table은 `AlreadyExistsException`, stale `VersionId`는
`ConcurrentModificationException`, 설정한 S3/카탈로그 persistence 실패는
`InternalServiceException`입니다. 문서화한 내부 순서에서 처음 발생한 오류가 이기며 실제 AWS의
순서를 비교하지 않습니다. 인증, 인가, IAM, Lake Formation, cross-account, cross-Region 오류는
범위 밖입니다.

<!-- section: configuration-observability -->
## 설정, logging, 수정 위치

Glue S3 어댑터는 `config/runtime/mystack.yaml`의 `localstack.endpoint_url`, region, credential, path-style
설정을 주입받습니다. Use case에 서비스/container 이름을 hard-code하지 않습니다. 구조화한
`glue.open_table_format.*`, `glue.iceberg_metadata.*` event가 유효성 검사, read/write/delete, 공개,
보상, 크기, 안전한 URI/document fingerprint, failure type, `fix_hint`를 기록합니다. Metadata body와
authorization 값은 logging하지 않습니다.

botocore, Glue, Iceberg upgrade 후 이 경로가 깨지면 다음 순서로 확인합니다.

1. Request member/nesting 변경: `glue/adapters/inbound/aws_table.py`
2. Type/action/transform/Iceberg spec 변경: `glue/domain/open_table_format.py`
3. 실행 순서/CAS/보상 변경: `glue/application/open_table_format.py`
4. LocalStack/S3 codec 또는 엔드포인트 변경: `glue/adapters/outbound/iceberg_metadata.py`
5. 실제 클라이언트 근거: `glue/tests/workloads/open_table_format.py`, typed pytest compatibility annotation

<!-- section: evidence -->
## 검증 근거와 한계

빠른 테스트는 nested type, global ID, 모든 layer 경계, 공식 boto3 serialization, modeled error,
결정적 JSON, 카탈로그 공개 실패 cleanup을 명시적 제한 시간으로 검증합니다. 기존 단일 Glue 5 Spark E2E
process에서 공개 Proxy를 거쳐 boto3로 생성하고 Iceberg GlueCatalog로 load/append한 뒤
`UpdateOpenTableFormatInput`으로 evolve하고 다시 load/append합니다. 마지막으로 Glue와 LocalStack S3
메타데이터를 확인합니다. 두 번째 Spark startup은 추가하지 않습니다. Image는 `PYSPARK_PYTHON`과
`PYSPARK_DRIVER_PYTHON`을 모두 hash-lock된 Mystack virtualenv로 지정하므로 Spark driver도 서비스와
동일한 고정 boto3 모델을 검증합니다. Upstream Glue image가 system interpreter를 미리 설정할 수
있으므로 Mystack `spark-submit` wrapper는 동일한 `spark.pyspark.python`과
`spark.pyspark.driver.python` property도 전달합니다. 실제 binary는
`MYSTACK_GLUE_SPARK_SUBMIT_BINARY`로 교체할 수 있고, 뒤에 전달한 command-line `--conf`로 default를
재정의할 수 있습니다. 이 선택은 Spark 공식 [PySpark property
계약](https://spark.apache.org/docs/3.5.4/configuration.html#available-properties)을 따릅니다.

이 프로필은 Iceberg v2만 지원합니다. Iceberg REST, PyIceberg, Flink, Trino, encryption-key 관리,
managed optimizer, 인증/인가, Lake Formation, cross-account, cross-Region은 제외합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue `OpenTableFormatInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html)
- [AWS Glue `CreateIcebergTableInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html)
- [AWS Glue `UpdateIcebergTableInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateIcebergTableInput.html)
- [AWS Glue `IcebergTableUpdate`](https://docs.aws.amazon.com/glue/latest/webapi/API_IcebergTableUpdate.html)
- [Apache Iceberg table metadata specification](https://iceberg.apache.org/spec/#table-metadata)
- [Apache Iceberg metastore serialization](https://iceberg.apache.org/spec/#metastore-serialization)
