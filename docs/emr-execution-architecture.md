<!-- doc-id: emr-execution-architecture -->
<!-- lang: en -->

[한국어](emr-execution-architecture.ko.md) | [English](emr-execution-architecture.md)

# EMR execution architecture

<!-- toc:start -->
## Contents

- [Request to cluster state](#request-to-cluster-state)
- [Bootstrap and Step execution](#bootstrap-and-step-execution)
- [Logs, termination, and local constraints](#logs-termination-and-local-constraints)
- [References](#references)
<!-- toc:end -->

<!-- section: request -->
## Request to cluster state

EMR clients send AWS JSON 1.1 requests to the public Proxy. The EMR inbound adapter validates the
pinned service model, maps the request to narrow application commands, and the cluster driver owns
the asynchronous state transitions. The Proxy does not know cluster or Step rules.

```text
boto3 / AWS CLI
       | ElasticMapReduce.*
       v
proxy:4566 -> emr:8080 -> AWS JSON adapter -> cluster/Step commands
                                              |              |
                                              v              v
                                      cluster state       queue driver
```

`RunJobFlow` creates a local cluster model. `AddJobFlowSteps` appends ordered Steps. Read calls
(`DescribeCluster`, `DescribeStep`, `ListClusters`, `ListSteps`) observe the same state machine;
`CancelSteps` and `TerminateJobFlows` signal the driver rather than bypassing it.

<!-- section: execution -->
## Bootstrap and Step execution

The driver serializes work for a cluster. Bootstrap actions finish before the cluster becomes
`WAITING`; a runnable Step then resolves its exact argument vector and starts a local Spark child
process. Arguments are never joined into a shell command.

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

`s3://` application, `--files`, `--py-files`, `--jars`, and archive inputs are materialized before
Spark starts. The runtime supplies the configured S3A endpoint and path-style settings. Cancellation
first requests child shutdown and then escalates within the configured deadline; runtime close also
cancels queued tasks, closes artifact clients, and releases driver locks.

<!-- section: logs -->
## Logs, termination, and local constraints

Live stdout/stderr are available through the EMR management read model. When `LogUri` is configured,
terminal controller, syslog, stdout, stderr, and local-driver streams are published under that S3
prefix. Publication retries are recorded separately from the Step result, so a completed Step can
still have pending log delivery.

```text
Spark child -> runtime logs -> management UI (live)
                    |
                    +-> LogUri S3 publisher -> compressed terminal artifacts
```

This is local-mode Spark, not an EC2/YARN/HDFS emulator: instance counts are request metadata and
do not provision workers. There is no Spark History Server or reconstruction of completed live UIs.
The EMR Console is unauthenticated by design for trusted local networks; do not expose it publicly.

<!-- section: references -->
## References

- [EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [EMR Spark Steps](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Spark application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
- [EMR LogUri contract](protocols/emr/emr-log-layout.md)
