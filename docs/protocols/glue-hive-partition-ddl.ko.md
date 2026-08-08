<!-- doc-id: protocols/glue-hive-partition-ddl -->
<!-- lang: ko -->

[한국어](glue-hive-partition-ddl.ko.md) | [English](glue-hive-partition-ddl.md)

# Glue를 통한 Spark Hive partition DDL

Mystack은 Spark SQL을 parse하지 않습니다. Spark 3.5가 DDL 문법, type 검사, `IF EXISTS`/
`IF NOT EXISTS`, S3 directory 탐색, cache 무효화, command 오류를 소유합니다. Mystack은 공식
Glue Hive metastore client가 사용하는 Glue catalog operation을 제공합니다. 이 경계는 AWS가
[Data Catalog를 외부 Hive
metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)로
설명한 내용을 따릅니다.

<!-- section: mapping -->
## DDL과 Glue mapping

| Spark/Hive 동작 | Glue catalog surface |
| --- | --- |
| `ADD PARTITION`, 다중 add | `CreatePartition`, `BatchCreatePartition` |
| 존재 여부 검사와 `SHOW PARTITIONS` | `GetPartition`, `BatchGetPartition`, `GetPartitions` |
| Partition rename과 `SET LOCATION` | `UpdatePartition`, `BatchUpdatePartition` |
| `DROP PARTITION` | `DeletePartition`, `BatchDeletePartition` |
| `MSCK REPAIR` / `RECOVER PARTITIONS` ADD | Spark가 S3를 scan한 뒤 발견한 Glue partition 생성 |
| `MSCK REPAIR ... DROP` | Spark가 S3와 Glue를 비교한 뒤 없는 Glue partition 삭제 |
| `MSCK REPAIR ... SYNC` | 한 Spark command에서 위 ADD와 DROP 경로 결합 |

DDL 형식과 type이 있는 partition literal은 공식 [Spark 3.5.4 `ALTER TABLE`
문서](https://spark.apache.org/docs/3.5.4/sql-ref-syntax-ddl-alter-table.html)를 따릅니다. Repair mode
동작은 공식 [Spark `REPAIR TABLE`
문서](https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-repair-table.html)를 따릅니다.

<!-- section: semantics -->
## Catalog와 side effect 의미론

Partition identity는 table `PartitionKeys` 순서의 tuple입니다. `/`, `=`, 공백, Unicode를 포함한
value를 string 그대로 보존합니다. Rename은 이 tuple을 변경하고 목적지가 이미 있으면 거부합니다.
`SET LOCATION`은 Hive client가 전달한 partition input으로 교체하면서 creation time을 유지합니다.
Partition mutation은 새 table version을 만들지 않습니다.

Glue batch API는 결정적 partial-success operation입니다. Entry를 request 순서로 실행하고 성공한
entry는 commit 상태로 남기며 실패한 각 entry는 `Errors`에 포함합니다. 단건 operation은 request
전체가 실패합니다. Spark가 API를 선택하기 전에 자체 preflight 검사를 할 수 있으므로 SQL 수준
exception은 Spark가 소유하고 최종 metadata는 Glue가 소유합니다.

Emulator에서 Glue metadata 호출은 S3 object를 생성·복사·rename·삭제하지 않습니다. Repair 탐색과
filesystem side effect는 Spark/Hadoop이 소유합니다. CI contract는 external table의 catalog
partition을 drop해도 기존 S3 data가 남는지 증명합니다. `SET LOCATION`은 data를 복사하지 않고
metadata만 갱신합니다.

<!-- section: diagnose -->
## 검증과 진단

실제 port를 사용하는 좁은 boto3 contract는 add, partial multi-add, rename, location update,
collision, partial delete, 복잡한 값, table version 불변을 검사합니다. CI 전용 Glue 5/Spark 3.5
scenario는 LocalStack S3를 대상으로 단건/다건 add, 두 `IF` 변형, rename, location update, drop,
기본/ADD/DROP/SYNC repair와 `ALTER TABLE RECOVER PARTITIONS`를 실행합니다. 각 SQL 경계 전후에
`MYSTACK_E2E_SCENARIO`를 출력하며 설정된 E2E timeout을 사용합니다.

이후 Spark나 Glue Hive client 변경에 대응할 때 generic AWS dispatcher의 operation 및 payload
fingerprint log와 repository transaction event를 먼저 확인합니다. SQL이 Mystack에 도착하지 않으면
Spark/Glue client 설정이나 E2E SQL을 수정합니다. Operation 요청 구조가 바뀌면 inbound partition/batch
operation family, metadata 규칙이 바뀌면 partition command나 batch application handler를
수정합니다. Repository adapter는 collection persistence만 유지합니다.

<!-- section: exclusions -->
## 제외 범위

Hive authorization, lock, transaction, statistics, crawler discovery, managed table data 삭제,
문서화되지 않은 client 동작은 여기서 보장하지 않습니다. 일반 인증·인가, Lake Formation,
cross-account, cross-Region 의미론도 프로젝트 범위 밖입니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue Data Catalog의 Spark SQL job 지원](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [AWS Glue Partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Spark 3.5.4 ALTER TABLE](https://spark.apache.org/docs/3.5.4/sql-ref-syntax-ddl-alter-table.html)
- [Spark REPAIR TABLE](https://spark.apache.org/docs/latest/sql-ref-syntax-ddl-repair-table.html)
