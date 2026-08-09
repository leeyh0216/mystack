<!-- doc-id: protocols/glue/glue-iceberg-commits -->
<!-- lang: ko -->

[한국어](glue-iceberg-commits.ko.md) | [English](glue-iceberg-commits.md)

# Iceberg GlueCatalog commit 계약

<!-- toc:start -->
## 목차

- [책임 경계](#책임-경계)
- [원자적 판단과 저장 순서](#원자적-판단과-저장-순서)
- [SQLite transaction 설정](#sqlite-transaction-설정)
- [Logging과 수정 위치](#logging과-수정-위치)
- [검증과 제외 범위](#검증과-제외-범위)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 Apache Iceberg 1.7.1이 Mystack Glue emulator에 commit할 때 사용하는 catalog pointer
부분을 정의합니다. AWS Glue 5.0에는 Iceberg 1.7.1이 포함되며 기본적으로 optimistic locking을
사용합니다. Iceberg AWS integration은 Glue table `VersionId`로 오래된 metadata pointer 교체를
거부한 뒤 refresh/retry합니다. [AWS Glue Iceberg 안내](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)와
[Iceberg AWS optimistic locking 계약](https://iceberg.apache.org/docs/1.7.1/aws/#optimistic-locking)을
기준으로 합니다.

<!-- section: responsibility -->
## 책임 경계

Mystack은 Glue catalog operation을 구현하며 Iceberg table format을 직접 구현하지 않습니다.
Spark/Iceberg가 data, manifest, metadata JSON, snapshot과 S3 object를 Iceberg 구현으로 생성합니다.
Mystack은 `UpdateTable`에 들어온 `TableInput`과 `Parameters.metadata_location`을 저장하고 요청의
`VersionId`가 현재 값일 때만 current catalog pointer를 원자적으로 바꿉니다. Iceberg metadata
file을 parse하거나 다시 쓰지 않습니다.

이 분리는 writer가 독립 metadata를 준비한 뒤 현재 metadata pointer를 원자적으로 교체한다는
Iceberg의 [reliability model](https://iceberg.apache.org/docs/1.7.1/reliability/#concurrent-write-operations)을
따릅니다.

<!-- section: algorithm -->
## 원자적 판단과 저장 순서

Durable update 하나는 다음 순서로 실행합니다.

1. AWS JSON 1.1 경계가 model에 따른 `UpdateTable` 요청을 검증합니다.
2. Short-lived SQLite connection이 설정한 foreign key, journal, synchronous, busy-timeout policy를
   적용하고 `BEGIN IMMEDIATE`를 시작합니다.
3. Application이 현재 정규화 table row를 찾고 요청 `VersionId`와 현재 값을 비교합니다.
4. 값이 일치하면 candidate 하나를 만듭니다. 전달받은 table definition이 current가 되고 정수
   version을 한 번 증가시키며 `SkipArchive=true`가 아니면 이전 version을 archive합니다.
5. Adapter가 이전 `VersionId`를 조건으로 current table을 update하고, 같은 transaction에서 archive와
   partition-key row를 쓰며 진단용 catalog revision을 증가시킨 뒤 commit합니다.
6. Connection을 닫습니다. Validation, 조건부 update, commit 중 하나라도 실패하면 SQLite transaction
   전체를 rollback합니다.

Stale writer는 save 전에 modeled `ConcurrentModificationException`으로 실패합니다. Validation, conflict,
persistence 실패는 candidate를 공개하지 않습니다. Commit 중 cancellation은 제한된 commit 결과를
기다린 뒤 durable candidate가 보이는지 판단합니다.

따라서 같은 base version에서 commit한 두 process는 version 1 winner 하나와 stale-version 실패
하나를 만듭니다. Iceberg client는 새 pointer를 refresh하고 자기 변경을 retry할 수 있습니다. 이는
catalog compare-and-swap이며 S3 data file 전체에 대한 global transaction isolation은 아닙니다.

<!-- section: configuration -->
## SQLite transaction 설정

`glue.sqlite.database_file`은 유일한 영속 catalog path입니다. WAL이 `-wal`, `-shm` sibling을
유지하므로 parent directory 전체를 write 가능하게 mount해야 합니다. `busy_timeout_milliseconds`는
busy writer wait 하나의 상한이고 `retry_limit`은 추가 short retry 횟수의 상한입니다. 경합 timeout은
partial change 없이 요청을 실패시킵니다. 검증한 기본값은 `journal_mode: wal`이며,
`journal_mode: rollback`은 명시적 escape hatch이고 자동 fallback이 아닙니다.

SQLite WAL은 같은 host와 같은 mounted directory에서 concurrent reader와 writer 하나를 지원합니다.
Multi-host deployment와 network filesystem은 이 계약의 범위 밖입니다. Driver 검증 절차, backup 절차,
checkpoint policy, mounted configuration 전체는 [Glue SQLite runtime
계약](glue-sqlite-runtime.ko.md)에 정의했습니다.

<!-- section: observability -->
## Logging과 수정 위치

`glue.iceberg.commit.begin`, `.version.accepted`, `.persist.before`, `.conflict`, `.succeeded`,
`.failed`는 expected/current/candidate version과 resource·metadata location의 SHA-256 앞부분만
기록합니다. S3 path, table body, credential, authorization header는 기록하지 않습니다.
`glue.sqlite_catalog.schema.*`, `.transaction.begin.*`, `.transaction.busy.retry`,
`.transaction.commit.*`, `.transaction.rolled_back`는 catalog storage 경계를 보여줍니다.

Spark/Iceberg client 변경으로 이 경로가 깨지면 다음 순서로 확인합니다.

1. Wire member 변경은 고정 botocore model 경계와 `glue/adapters/inbound/aws_table.py`
2. `VersionId`, archive, `SkipArchive` 판단은 `CatalogTable.revise`와 `glue/application/table.py`
3. Iceberg 식별과 안전한 commit event는 `glue/application/iceberg_commit.py`
4. Process 간 lost update, writer 경합, schema mapping, commit/rollback은
   `glue/adapters/outbound/sqlite_catalog/`과 `glue.sqlite` 설정
5. 실제 client retry 변화는 `glue/tests/workloads/iceberg_contention_job.py`와 생성된 compatibility case

<!-- section: evidence -->
## 검증과 제외 범위

빠른 `glue/tests/test_iceberg_commit.py`는 같은 base version의 spawn process 두 개를 실행합니다.
모든 wait를 설정 가능하게 제한하고 winner 하나, conflict 하나, foreign-key 무결성, archive policy와
상한이 있는 SQLite writer 경합을 검증합니다. CI는 별도 Glue-image container 두 개에서 실제 Spark
3.5.4/Iceberg 1.7.1
writer를 public Proxy로 실행하고 retry된 append 둘이 모두 보존되는지 확인합니다. One-off container
동작은 Docker Compose 공식 [`run` 문서](https://docs.docker.com/reference/cli/docker/compose/run/)를
따릅니다.
Partition, schema, sort, identifier evolution도 이 pointer commit을 그대로 사용하며 별도
[Iceberg evolution 계약](glue-iceberg-evolution.ko.md)으로 검증합니다.
Row-level COW/MOR commit도 같은 경로를 사용하며 [Iceberg row-level DML
계약](glue-iceberg-row-level-dml.ko.md)으로 검증합니다.
Snapshot/reference/procedure commit도 같은 경로를 사용하며 [Iceberg snapshot/reference/procedure
계약](glue-iceberg-snapshots-refs-procedures.ko.md)으로 검증합니다.
Rename/drop/purge는 [Iceberg lifecycle 계약](glue-iceberg-lifecycle.ko.md)에 정리한 순서를
사용합니다.

이 계약 자체는 Iceberg SQL 의미론을 정의하지 않습니다. Open Table Format input은 별도
[입력 계약](glue-open-table-format.ko.md)에서 다룹니다. Managed optimizer, Lake Formation,
인증·인가, cross-account/cross-Region, PyIceberg, Flink, Trino는 범위가 아닙니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue에서 Iceberg 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
- [Apache Iceberg 1.7.1 AWS integration](https://iceberg.apache.org/docs/1.7.1/aws/)
- [Apache Iceberg 1.7.1 reliability](https://iceberg.apache.org/docs/1.7.1/reliability/)
- [AWS Glue `UpdateTable`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [AWS Glue `TableVersion`](https://docs.aws.amazon.com/glue/latest/webapi/API_TableVersion.html)
- [SQLite transaction](https://www.sqlite.org/lang_transaction.html)
- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
