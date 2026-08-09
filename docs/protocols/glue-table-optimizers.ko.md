<!-- doc-id: protocols/glue-table-optimizers -->
<!-- lang: ko -->

[한국어](glue-table-optimizers.ko.md) | [English](glue-table-optimizers.md)

# Glue managed table optimizer protocol

<!-- toc:start -->
## 목차

- [사용자에게 보이는 계약](#사용자에게-보이는-계약)
- [기본값과 검증](#기본값과-검증)
- [Scheduler와 Spark 실행](#scheduler와-spark-실행)
- [설정과 변경 시 수정 위치](#설정과-변경-시-수정-위치)
<!-- toc:end -->

<!-- section: user-contract -->
## 사용자에게 보이는 계약

Mystack은 AWS 공식 [table optimizer API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html)의
`CreateTableOptimizer`, `GetTableOptimizer`, `UpdateTableOptimizer`, `DeleteTableOptimizer`,
`BatchGetTableOptimizer`, `ListTableOptimizerRuns` 여섯 operation을 구현합니다. 일반 boto3 요청을
공개 Proxy endpoint로 보내면 됩니다. Catalog metadata의 S3 값은 보통의 `s3://bucket/key` URI로
적고 LocalStack HTTP endpoint를 넣지 않습니다.

```python
glue.create_table_optimizer(
    CatalogId="000000000000",
    DatabaseName="analytics",
    TableName="events",
    Type="compaction",
    TableOptimizerConfiguration={
        "enabled": True,
        "compactionConfiguration": {
            "icebergConfiguration": {
                "strategy": "binpack",
                "minInputFiles": 5,
                "deleteFileThreshold": 1,
            }
        },
    },
)
```

`Parameters.table_type=ICEBERG`이고 absolute `StorageDescriptor.Location`이 있는 Iceberg table만
대상입니다. Compaction은 AWS 공식 [optimizer 제한](https://docs.aws.amazon.com/glue/latest/dg/optimizer-notes.html)과
같이 Parquet table만 받습니다. `roleArn`과 VPC connection field는 AWS 입력 구조를 검증하고 보존하지만,
IAM과 인가가 Mystack 범위 밖이므로 권한이나 network isolation 의미는 없습니다.

<!-- section: defaults -->
## 기본값과 검증

Domain은 AWS 공식 [optimizer 개요](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html)의
기본값을 정규화합니다.

| 유형 | 기본값과 제한 |
| --- | --- |
| `compaction` | `binpack`, `minInputFiles=100`, `deleteFileThreshold=1`; worker가 연속 네 번 실패하면 비활성화 |
| `retention` | 5일, snapshot 1개 유지, 만료 file 정리, 24시간 주기; 주기는 3–168시간 |
| `orphan_file_deletion` | 3일, table location, 24시간 주기; 주기는 3–168시간; location은 table path 자체 또는 실제 하위 path |

Botocore 입력 구조 검증이 handler보다 먼저 실행됩니다. Table과 무관한 domain value는 parent 조회,
duplicate, mutation보다 먼저 immutable draft로 parse합니다. Iceberg 대상 여부, file format, 기본
location, location 포함 관계는 table 조회 뒤 mutation 전에 결합합니다. Table/optimizer가 없으면
`EntityNotFoundException`, 중복 create는
`AlreadyExistsException`, type/config/location이 잘못되면 `InvalidInputException`입니다.
`BatchGetTableOptimizer`는 최대 20개 entry를 받고 항목별 `ErrorDetail` 실패를 반환합니다. 실행
가능한 전체 순서는 생성된 [오류 matrix](../compatibility/glue-errors.ko.generated.md)에 있습니다.
인증·인가·IAM·Lake Formation·cross-account·cross-Region 분기는 의도적으로 없습니다.

<!-- section: execution -->
## Scheduler와 Spark 실행

활성 optimizer는 durable schedule에 들어갑니다. Claim 하나가 `starting`에서 `in_progress`로,
이후 `completed` 또는 `failed`로 이동합니다. 재시작 때 남아 있는 active run은 `failed`로
복구합니다. 소유 table/database의 rename과 delete에는 optimizer 및 history가 같은 atomic
transaction으로 포함됩니다. Update/delete로 기존 claim이 stale해지면 scheduler가 subprocess를
종료합니다. History는 설정한 상한까지 catalog schema 3에 보존합니다.

Claim마다 timeout이 있는 Glue 5 `spark-submit` process 하나를 실행합니다. Worker는 Apache
Iceberg 1.7.1 공식 [Spark procedure](https://iceberg.apache.org/docs/1.7.1/spark-procedures/)를
사용합니다.

| Optimizer | 실행 mapping |
| --- | --- |
| compaction | `rewrite_data_files`; `z-order`는 현재 Iceberg sort order의 identity column을 해석해 Iceberg 공식 형식인 `sort_order => 'zorder(...)'` 인자를 전달 |
| retention, file 정리 활성 | `expire_snapshots` Spark procedure |
| retention, file 정리 비활성 | Iceberg `ExpireSnapshots.cleanExpiredFiles(false)` Java API로 data file 삭제 방지 |
| orphan 삭제 | `remove_orphan_files` dry-run 후보를 S3 수정 시각으로 다시 검사해 삭제하며 optimizer 생성 전·생성 시점 file은 보존 |

Glue는 `sort`, `z-order` 모두 기존 Iceberg sort order를 요구합니다. Emulator는 API 설정 생성은
허용하고 예약 실행이 시작될 때 실제 runtime metadata를 검증합니다. Table에 sort order가 없으면
z-order run은 진단 가능한 `failed` 기록을 남깁니다. 이번 버전은 z-order에 identity sort field를
지원하며 transformed sort field는 계층 sort로 조용히 강등하지 않고 명시적으로 실패합니다.
이 호환 경계는 `mystack.glue.runtime.table_optimizer_job`에 있습니다.

Run별 `work.json`, `stdout.log`, `stderr.log`는 `glue.table_optimizers.work_root` 아래에 둡니다.
Work file mode는 `0600`이며 payload 내용과 credential은 structured log에 복사하지 않습니다.
Boundary log에는 run ID, optimizer type, timeout, endpoint host, result metric 이름과 수정 안내가
있습니다. Timeout이면 Spark process group 전체를 terminate하고 grace period 뒤 kill합니다. Local mode의 AWS DPU metric은
0이며 가능한 file/byte/delete count와 duration은 Iceberg 결과에서 얻습니다.

<!-- section: repair -->
## 설정과 변경 시 수정 위치

Scheduler와 process 값은 모두 mounted YAML의 `glue.table_optimizers` 아래에 있습니다. 전체 block은
[설정 안내](../configuration.ko.md)를 참고하세요. 의존 방향은 다음과 같습니다.

```text
AWS JSON adapter -> optimizer use case -> optimizer domain
                                    -> executor port <- Spark subprocess adapter
composition root -> scheduler runtime -> use case + executor port
```

상위 버전 변경으로 깨지면 structured `fix_hint`에서 다음의 가장 좁은 owner를 찾습니다.

- boto3 요청/응답 구조: `adapters/inbound/aws_optimizer.py`, `aws_shapes.py`
- 오류 선택과 순서: domain/application, `contracts/glue-error-conditions.yaml`
- lifecycle과 기본값: `domain/table_optimizer.py`
- scheduling과 cancel: `application/table_optimizer_runtime.py`
- Spark command와 결과 decode: `adapters/outbound/table_optimizer_executor.py`
- Iceberg procedure 또는 Glue 5 runtime: `runtime/table_optimizer_job.py`
- durable format: repository schema migration과 persistence test

세 유형의 실제 Glue 5/Spark 3.5.4/LocalStack 실행은 CI에서만 수행합니다. Local unit test는 fake
executor와 명시적 timeout을 사용하며 public Proxy boto3 suite는 여섯 API 전부를 실행합니다.
