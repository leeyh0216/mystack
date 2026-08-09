<!-- doc-id: protocols/glue-iceberg-commits -->
<!-- lang: ko -->

[한국어](glue-iceberg-commits.ko.md) | [English](glue-iceberg-commits.md)

# Iceberg GlueCatalog commit 계약

<!-- toc:start -->
## 목차

- [책임 경계](#책임-경계)
- [원자적 판단과 저장 순서](#원자적-판단과-저장-순서)
- [File lock 설정](#file-lock-설정)
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
2. Repository가 process-local asynchronous mutex와 설정된 POSIX advisory file lock을 얻습니다.
3. 두 lock을 보유한 상태에서 disk의 최신 JSON catalog revision을 다시 읽습니다.
4. Application이 table을 찾고 요청 `VersionId`와 현재 값을 비교합니다.
5. 값이 일치하면 candidate 하나를 만듭니다. 전달받은 table definition이 current가 되고 정수
   version을 한 번 증가시키며 `SkipArchive=true`가 아니면 이전 version을 archive합니다.
6. 같은 directory의 temporary document를 쓰고 fsync한 뒤 state file을 원자적으로 교체합니다.
   Directory fsync도 시도하며, 이 작업이 끝난 뒤에만 candidate를 visible state로 공개합니다.
7. File lock과 process-local mutex 순서로 해제합니다.

Stale writer는 save 전에 modeled `ConcurrentModificationException`으로 실패합니다. Validation, conflict,
persistence 실패는 candidate를 공개하지 않습니다. Save 중 cancellation은 제한된 save 결과를
기다린 뒤 commit 여부에 맞춰 visible state를 결정합니다. Lock acquisition/release worker thread도
보호하므로 cancellation이 잠긴 descriptor를 남기지 않습니다.

따라서 같은 base version에서 commit한 두 process는 version 1 winner 하나와 stale-version 실패
하나를 만듭니다. Iceberg client는 새 pointer를 refresh하고 자기 변경을 retry할 수 있습니다. 이는
catalog compare-and-swap이며 S3 data file 전체에 대한 global transaction isolation은 아닙니다.

<!-- section: configuration -->
## File lock 설정

`glue.catalog_lock.file`, `acquire_timeout_seconds`, `poll_interval_seconds`는 필수 YAML 설정입니다.
상대 path는 `glue.data_root` 아래에서 해석합니다. Lock file은 `glue.state_file`과 달라야 하며 poll
interval은 acquisition timeout보다 클 수 없습니다. 같은 state file을 공유하는 모든 Glue emulator
process는 POSIX `flock`을 보장하는 filesystem의 같은 lock file을 사용해야 합니다. 기반 primitive는
Python 공식 [`fcntl.flock`](https://docs.python.org/3/library/fcntl.html#fcntl.flock) 문서를 따릅니다.

Lock wait에는 상한이 있고 timeout은 state를 바꾸지 않습니다. Lock file을 삭제하지 않는 이유는
unlink/recreate 시 동시 process가 서로 다른 inode를 잠글 수 있기 때문입니다. Docker/Linux와 local
POSIX host를 지원합니다. Multi-host distributed lock과 advisory lock이 안정적이지 않은 filesystem은
이 계약의 범위 밖입니다.

<!-- section: observability -->
## Logging과 수정 위치

`glue.iceberg.commit.begin`, `.version.accepted`, `.persist.before`, `.conflict`, `.succeeded`,
`.failed`는 expected/current/candidate version과 resource·metadata location의 SHA-256 앞부분만
기록합니다. S3 path, table body, credential, authorization header는 기록하지 않습니다.
`glue.repository.process_lock.*`, `.external_state.refresh.after`, `.transaction.*`, `.persist.*`는
lock/reload/save 경계를 보여줍니다.

Spark/Iceberg client 변경으로 이 경로가 깨지면 다음 순서로 확인합니다.

1. Wire member 변경은 고정 botocore model 경계와 `glue/adapters/inbound/aws_table.py`
2. `VersionId`, archive, `SkipArchive` 판단은 `CatalogTable.revise`와 `glue/application/table.py`
3. Iceberg 식별과 안전한 commit event는 `glue/application/iceberg_commit.py`
4. Process 간 lost update, lock timeout, reload, fsync, replacement는
   `glue/adapters/outbound/repository.py`와 `glue.catalog_lock` 설정
5. 실제 client retry 변화는 `glue/scripts/e2e/iceberg_contention_job.py`와 생성된 compatibility case

<!-- section: evidence -->
## 검증과 제외 범위

빠른 `glue/tests/test_iceberg_commit.py`는 같은 base version의 spawn process 두 개를 실행합니다.
모든 wait를 설정 가능하게 제한하고 winner 하나, conflict 하나, 유효한 JSON, archive policy와
상한이 있는 lock timeout을 검증합니다. CI는 별도 Glue-image container 두 개에서 실제 Spark
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
- [Python `fcntl`](https://docs.python.org/3/library/fcntl.html)
