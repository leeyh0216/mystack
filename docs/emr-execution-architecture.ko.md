<!-- doc-id: emr-execution-architecture -->
<!-- lang: ko -->

[한국어](emr-execution-architecture.ko.md) | [English](emr-execution-architecture.md)

# EMR 실행 아키텍처

<!-- toc:start -->
## 목차

- [요청에서 cluster 상태까지](#요청에서-cluster-상태까지)
- [Bootstrap과 Step 실행](#bootstrap과-step-실행)
- [로그, 종료, 로컬 제약](#로그-종료-로컬-제약)
- [참고 자료](#참고-자료)
<!-- toc:end -->

<!-- section: request -->
## 요청에서 cluster 상태까지

EMR 클라이언트는 공개 Proxy에 AWS JSON 1.1 요청을 보냅니다. EMR inbound 어댑터가 고정 서비스 모델을
검증하고 좁은 application command로 변환하며 cluster driver가 비동기 상태 전이를 소유합니다. Proxy는
cluster나 Step 규칙을 알지 않습니다.

```text
boto3 / AWS CLI
       | ElasticMapReduce.*
       v
proxy:4566 -> emr:8080 -> AWS JSON adapter -> cluster/Step command
                                              |              |
                                              v              v
                                      cluster state       queue driver
```

`RunJobFlow`는 로컬 cluster 모델을 만들고 `AddJobFlowSteps`는 순서가 있는 Step을 추가합니다. Read 호출은
같은 state machine을 관찰하며 취소와 종료는 driver를 우회하지 않고 signal을 보냅니다.

<!-- section: execution -->
## Bootstrap과 Step 실행

Driver는 cluster별 작업을 직렬화합니다. Bootstrap action은 cluster가 `WAITING`이 되기 전에 끝나며,
runnable Step은 정확한 argument vector를 해석하고 로컬 Spark child process를 시작합니다. Argument를
shell command 문자열로 합치지 않습니다.

```text
RunJobFlow BootstrapActions / AddJobFlowSteps
                    |
                    v
        S3 artifact resolver (LocalStack)
                    |
                    v
 work directory + exact spark-submit/PySpark argv
                    |
                    v
 local Spark process -> stdout/stderr -> Step terminal state
```

`s3://` application, `--files`, `--py-files`, `--jars`, archive input은 Spark 시작 전에 materialize됩니다.
취소는 child shutdown을 요청한 뒤 설정 deadline 안에서 escalation하며 실행 환경 close는 queued task와
산출물 클라이언트, driver lock을 정리합니다.

<!-- section: logs -->
## 로그, 종료, 로컬 제약

Live stdout/stderr는 EMR management read 모델에서 볼 수 있습니다. `LogUri`가 있으면 terminal controller,
syslog, stdout, stderr, 로컬-driver stream을 해당 S3 prefix에 게시합니다. Step 결과와 로그 게시 retry는
분리돼 완료된 Step의 로그 delivery가 pending일 수 있습니다.

```text
Spark child -> runtime log -> management UI (live)
                    |
                    +-> LogUri S3 publisher -> compressed terminal artifact
```

이는 EC2/YARN/HDFS emulator가 아닌 로컬-mode Spark입니다. instance count는 worker를 만들지 않는 요청
메타데이터이며 Spark History Server와 종료된 live UI 복원은 제공하지 않습니다. Console은 신뢰하는 로컬
network에서만 쓰도록 인증 없이 설계됐습니다.

<!-- section: references -->
## 참고 자료

- [EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [EMR Spark Step](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Spark application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
- [EMR LogUri 계약](protocols/emr/emr-log-layout.ko.md)
