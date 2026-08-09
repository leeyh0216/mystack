<!-- doc-id: protocols/glue/glue-hive-table-alter -->
<!-- lang: ko -->

[한국어](glue-hive-table-alter.ko.md) | [English](glue-hive-table-alter.md)

# Glue를 통한 Spark Hive table ALTER

<!-- toc:start -->
## 목차

- [SQL과 protocol mapping](#sql과-protocol-mapping)
- [Glue API와 persistence 의미론](#glue-api와-persistence-의미론)
- [검증과 진단](#검증과-진단)
- [제외 범위](#제외-범위)
- [공식 출처](#공식-출처)
<!-- toc:end -->

Mystack은 Spark와 공식 Glue Hive metastore client가 선택한 Glue catalog 요청을 보존하며 Spark
SQL을 직접 parse하지 않습니다. SQL 분석, V1/V2 capability 검사, cache invalidation, SQL 예외는
Spark 책임입니다. `UpdateTable`, 불변 table version, 원자적 catalog persistence는 Mystack
책임입니다. 이 경계는 AWS가 문서화한 [Data Catalog 외부 Hive metastore
연동](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)을
따릅니다.

<!-- section: mapping -->
## SQL과 protocol mapping

| Spark Hive operation | 관찰되는 protocol 경계 | Mystack 보장 |
| --- | --- | --- |
| Complex Glue type 문자열을 포함한 `ADD COLUMNS` | `GetTable` 후 전체 `TableInput`을 넣은 `UpdateTable` | 손실 없는 교체와 새 table version |
| `ALTER/CHANGE COLUMN ... COMMENT` | `UpdateTable` | 기존 이름/type/순서를 유지하고 comment 변경 |
| `SET/UNSET TBLPROPERTIES` | `UpdateTable` | Spark가 보낸 전체 parameter map 보존 |
| `SET SERDE` / `SET SERDEPROPERTIES` | `UpdateTable` | SerDe class와 property map 보존 |
| Table `SET LOCATION` / `SET FILEFORMAT` | `UpdateTable` | StorageDescriptor 교체 보존, S3 object는 이동하지 않음 |
| Partition location/Serde 변경 | Partition API | [Partition DDL 계약](glue-hive-partition-ddl.ko.md)에서 검증 |
| V1 `DROP COLUMN`, `RENAME COLUMN`, `REPLACE COLUMNS`, type 변경 | Spark가 Glue 호출 전에 거부 | 실패 후 catalog state 불변 |
| Hive table `RENAME TO` | 공식 Glue Hive client가 `UpdateTable` 전에 거부 | `Table rename is not supported`, source metadata 유지 |

Spark 문서는 `DROP COLUMN`, `RENAME COLUMN`, `REPLACE COLUMNS`를 V2 전용으로 규정합니다.
Spark 3.5의 V1 `AlterTableChangeColumnCommand`는 comment/default 변경을 허용하지만 column 이름이나
type 변경은 거부합니다. 공식 Glue Hive client의 `alterTable`도 table 이름 변경을 별도로
거부합니다. 이는 client 소유 결과이므로 Mystack이 비공개 SQL parser를 추가하거나 존재하지
않는 AWS 요청을 만들어내지 않습니다.

<!-- section: semantics -->
## Glue API와 persistence 의미론

`UpdateTable`은 저장된 정의를 완전한 `TableInput`으로 교체하며 누락된 field를 merge하지
않습니다. Hive 호환성을 위해 이름은 소문자로 정규화하고 column과 type 문자열은 손실 없이
보존합니다. 기본값에서는 이전 정의가 archived `TableVersion`이 되고 현재 숫자 `VersionId`가
증가합니다. `SkipArchive=true`는 교체된 정의를 보관하지 않고 현재 version만 증가시킵니다.
전달된 `VersionId`는 compare-and-swap 선행 조건입니다.

현재 Glue model은 최상위 `UpdateTable.Name`도 제공합니다. 이는 공식 Hive client가 사용하는
rename 경로가 아니라 직접 Glue API surface입니다. `Name`이 source를 가리키고
`TableInput.Name`이 다르면 Mystack은 table과 모든 catalog partition을 원자적으로 이동합니다.
Source가 없으면 실패하고, 기존 target은 덮어쓰지 않으며, 대소문자만 다른 변경은 동일한 Hive
이름으로 정규화합니다. `UpdateTable`에는 `DatabaseName`이 하나뿐이므로 database 사이 이동은
불가능합니다. Persistence 실패 시 candidate table과 이동한 partition 모두 공개하지 않습니다.

Catalog metadata 변경은 S3 data를 copy, rename, delete하지 않습니다. Filesystem side effect는
Spark/Hadoop 책임입니다. 권한, lock, 통계 정합성, cache 동작은 emulator catalog 경계 밖입니다.

<!-- section: diagnose -->
## 검증과 진단

실제 port를 사용하는 작은 boto3 계약은 전체 StorageDescriptor/complex column 보존, property,
SerDe, location, 기본 archive, `SkipArchive`, 낙관적 version 검사, 직접 API rename, target 충돌,
대소문자 정규화, source 부재, partition 보존을 검증합니다. Persistence 계약은 durable save
실패를 주입하여 table과 partition 이름이 함께 rollback되는 것을 증명합니다.

CI 전용 Glue 5/Spark 3.5 시나리오는 Spark session 하나를 재사용합니다. 성공하는 column,
property, SerDe, location 변경을 실행한 뒤 V1 drop/rename/type 변경과 Hive table rename이
실패하고 최종 Glue 정의가 변하지 않는지 확인합니다. 각 SQL 경계는 구조화한
`MYSTACK_E2E_SCENARIO` event를 출력하며 설정된 E2E timeout을 상속합니다.

향후 Spark 또는 Glue client 변경으로 깨지면 먼저 범용 AWS dispatcher log에 `UpdateTable`이
있는지 확인합니다. 요청이 없으면 Spark/client adapter 또는 SQL 기대값 변경입니다. Payload가
달라졌으면 inbound table operation family나 botocore 계약을 수정합니다. Payload가 맞지만 state가
틀리면 `TableCommands`, serialization/restart 문제면 repository adapter를 확인합니다. Protocol
translation, application policy, persistence 책임을 이 순서로 분리합니다.

<!-- section: exclusions -->
## 제외 범위

Spark V1 Hive catalog에 V2 column operation을 추가하거나 Hive lock·권한을 흉내 내거나 managed
table data를 이동하거나 실 AWS 계정과 동작을 비교하지 않습니다. 인증, 인가, IAM, Lake
Formation, cross-account, cross-Region 의미론도 범위 밖입니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue UpdateTable](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue GetTableVersions](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersions.html)
- [AWS Glue Data Catalog Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark 3.5 ALTER TABLE](https://spark.apache.org/docs/3.5.7/sql-ref-syntax-ddl-alter-table.html)
- [Spark 3.5.4 V1 ALTER 구현](https://github.com/apache/spark/blob/v3.5.4/sql/core/src/main/scala/org/apache/spark/sql/execution/command/ddl.scala)
- [공식 Glue Hive client `alterTable`](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/branch-3.4.0/aws-glue-datacatalog-client-common/src/main/java/com/amazonaws/glue/catalog/metastore/GlueMetastoreClientDelegate.java)
