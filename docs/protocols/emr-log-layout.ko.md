<!-- doc-id: emr-log-layout -->
<!-- lang: ko -->

[한국어](emr-log-layout.ko.md) | [English](emr-log-layout.md)

# EMR LogUri S3 배치

`RunJobFlow.LogUri`가 S3 URI이면 Mystack은 terminal Step의 process log를 보관합니다. Step
경로는 Amazon EMR이 문서화한 S3 배치를 따릅니다. Spark는 local/client mode로 실행되므로
`containers/` 아래 application ID는 의도적으로 만든 synthetic ID이며 YARN application을
의미하지 않습니다.

<!-- section: enable -->
## Log 보관 활성화

Cluster를 만들 때 bucket과 선택적 prefix를 지정합니다. Bucket은 설정한 LocalStack S3에 먼저
존재해야 합니다.

```python
cluster = emr.run_job_flow(
    Name="local-spark",
    LogUri="s3://my-logs/team-a/",
    Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
)
```

`LogUri`를 생략하면 S3 log mutation이 없습니다. URI가 잘못됐거나 bucket을 사용할 수 없어도
Spark 결과를 덮어쓰지 않습니다. Console log tab 또는
`GET /_mystack/components/emr/logs?cluster_id=...&step_id=...`에서 publication record를 확인합니다.

<!-- section: layout -->
## Object 배치

`LogUri=s3://my-logs/team-a/`, cluster `j-ABC`, Step `s-123`이면 다음 object를 씁니다.

```text
s3://my-logs/team-a/j-ABC/steps/s-123/controller.gz
s3://my-logs/team-a/j-ABC/steps/s-123/syslog.gz
s3://my-logs/team-a/j-ABC/steps/s-123/stdout.gz
s3://my-logs/team-a/j-ABC/steps/s-123/stderr.gz
s3://my-logs/team-a/j-ABC/containers/application_local_j_ABC_s_123/
  container_local_j_ABC_s_123_01_000001/stdout.gz
  container_local_j_ABC_s_123_01_000001/stderr.gz
```

6개 object 모두 `Content-Encoding: gzip`을 사용합니다. `stdout`, `stderr`는 local
`spark-submit` process stream 원문입니다. `controller`는 local process 시작/종료를 투영합니다.
`syslog`는 EC2 node, YARN, node syslog가 없음을 명시합니다. Application object 2개는 local/client
driver stream을 복제하며 executor/container log 집계를 지원한다고 주장하지 않습니다.

Amazon EMR은 Step log를 `<cluster-id>/steps/<step-id>/`, YARN container log를
`<cluster-id>/containers/` 아래에 둔다고 문서화합니다. Client mode Spark driver output은 Step
log에 있고 cluster mode driver output은 application master에 있다고도 설명합니다. Mystack은
local/client runtime에서 표현할 수 있는 관찰 경로를 구현하고 차이를 명시합니다.

<!-- section: outcomes -->
## 성공, 실패, 취소

Local process가 종료되거나 Step 준비가 실패한 뒤, 결과 terminal Step 상태가 관찰되기 전에
게시합니다. 따라서 `LogUri`가 유효하면 성공, 0이 아닌 종료, 누락 artifact, 사용자 취소 모두
같은 object 이름 집합을 만듭니다. 준비 실패는 process stream이 비어 있고 `controller`와
publication record의 `process_started=false`로 표시합니다. 취소한 process의 실제 signal 종료
code를 기록하며 `CANCELLED`와 `FAILED`의 판정 권한은 EMR 상태 machine에 있습니다.

Local `<work_root>/<cluster-id>/<step-id>/log-publication.json`은 schema version 1이며 다음 상태 중
하나를 가집니다.

| 상태 | 의미 |
| --- | --- |
| `published` | 모든 Step/application object를 올렸으며 `published_keys`가 완전함 |
| `failed` | Upload가 중단됐으며 `published_keys`, 오류 type과 복구 정보로 부분 작업을 설명함 |
| `skipped` | `LogUri`가 없어 S3 log 쓰기를 시도하지 않음 |
| `pending` | Management API에 아직 record가 없으며 일반적으로 Step 실행 중임 |
| `unreadable` | Local record가 잘못됐거나 읽을 수 없으며 응답에 수정 hint가 있음 |

<!-- section: boundaries -->
## 구현 및 수정 경계

- S3 배치, gzip payload, 실패 record: `mystack.emr.adapters.outbound.logs`
- Process capture와 publication 호출 경계: `mystack.emr.adapters.outbound.runtime`
- Console/API 투영: `mystack.emr.adapters.inbound.management`
- Runtime client 소유권과 close 순서: `mystack.emr.runtime`, `mystack.emr.app`
- boto3/LocalStack Docker 검증: `tests/e2e/test_emr_spark.py`

AWS의 문서화된 directory 계약이 바뀌면 집중된 log adapter, 이 문서, unit test와 Docker E2E를
함께 수정합니다. S3 책임을 Domain, repository 또는 AWS request mapper로 옮기지 않습니다.

<!-- section: sources -->
## 공식 참고 자료

- [Amazon EMR: Log file 보기](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)
- [Amazon EMR: Cluster debug](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html)
- [Amazon EMR: Spark 작업 제출](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Amazon EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
