<!-- doc-id: emr-guide -->
<!-- lang: ko -->

[한국어](emr.ko.md) | [English](emr.md)

# Amazon EMR

<!-- toc:start -->
## 목차

- [Cluster 만들기](#cluster-만들기)
- [Bootstrap action으로 cluster 준비하기](#bootstrap-action으로-cluster-준비하기)
- [전체 Spark 또는 PySpark 인자 벡터 제출하기](#전체-spark-또는-pyspark-인자-벡터-제출하기)
- [Step 추적 및 log 확인](#step-추적-및-log-확인)
- [Image 준비 또는 시작 시 cluster provision](#image-준비-또는-시작-시-cluster-provision)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 로컬 EMR cluster를 만들고 bootstrap action으로 준비한 뒤 LocalStack S3의 코드와 데이터를
사용하는 Spark 또는 PySpark application을 실행하는 방법을 안내합니다.

<!-- section: cluster -->
## Cluster 만들기

다른 AWS client와 같은 host endpoint를 사용합니다. `LogUri`는 선택 사항이지만, terminal Step log를
LocalStack S3에 남기려면 bucket을 먼저 만들어야 합니다. 아래 release label은 기본 설정 profile이므로,
다른 label을 사용한다면 [설정](configuration.ko.md)에서 선택합니다.

```python
import boto3

s3 = boto3.client("s3", endpoint_url="http://localhost:4566", region_name="us-east-1")
emr = boto3.client("emr", endpoint_url="http://localhost:4566", region_name="us-east-1")

s3.create_bucket(Bucket="mystack-example")
created = emr.run_job_flow(
    Name="local-analytics",
    ReleaseLabel="emr-7.8.0",
    Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
    Applications=[{"Name": "Spark"}],
    LogUri="s3://mystack-example/logs/",
)
cluster_id = created["JobFlowId"]
```

`KeepJobFlowAliveWhenNoSteps=True`이면 나중에 `AddJobFlowSteps`를 호출할 수 있도록 cluster가 준비 상태로
남습니다. Emulator는 EMR container 안에서 Spark 3.5 local mode로 실행합니다. Instance count는 EMR
요청을 모델링하지만 EC2나 YARN worker를 만들지는 않습니다.

<!-- section: bootstrap -->
## Bootstrap action으로 cluster 준비하기

Script를 LocalStack S3에 올리고 `RunJobFlow`의 `BootstrapActions`로 참조합니다. Mystack은 script를
내려받아 `hadoop` 사용자로 실행합니다. Bootstrap action에서 virtual environment를 만들 수 있으며,
root 수준 변경이 필요할 때만 `sudo`를 사용합니다.

```bash
#!/usr/bin/env bash
set -euo pipefail

venv=/home/hadoop/project-venv
python3.11 -m venv "$venv"
"$venv/bin/python" -m pip --version
# 환경에서 제공하는 application dependency는 이 위치에서 설치합니다.
```

```python
s3.upload_file("bootstrap.sh", "mystack-example", "bootstrap/bootstrap.sh")

created = emr.run_job_flow(
    Name="prepared-local-analytics",
    ReleaseLabel="emr-7.8.0",
    Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
    Applications=[{"Name": "Spark"}],
    BootstrapActions=[
        {
            "Name": "create-project-venv",
            "ScriptBootstrapAction": {
                "Path": "s3://mystack-example/bootstrap/bootstrap.sh",
                "Args": [],
            },
        }
    ],
)
cluster_id = created["JobFlowId"]
```

`describe_cluster(ClusterId=cluster_id)`가 `WAITING`을 반환할 때까지 기다린 뒤 Step을 추가합니다.
Bootstrap의 종료 code가 0이 아니면 cluster 시작이 실패합니다.

<!-- section: submit -->
## 전체 Spark 또는 PySpark 인자 벡터 제출하기

Spark Step은 `command-runner.jar`로 제출합니다. `Args`는 shell 문자열이 아니라 인자 벡터입니다. 첫
항목은 `spark-submit`이고 option은 application보다 앞에 두며 뒤의 항목은 application 인자입니다.
PySpark workload는 interactive `pyspark` shell이 아니라 `spark-submit`으로 제출하는 Python application입니다.

```python
s3.upload_file("main.py", "mystack-example", "jobs/main.py")
s3.upload_file("shared.zip", "mystack-example", "jobs/shared.zip")
s3.upload_file("settings.json", "mystack-example", "jobs/settings.json")

step_ids = emr.add_job_flow_steps(
    JobFlowId=cluster_id,
    Steps=[
        {
            "Name": "daily-pyspark-transform",
            "ActionOnFailure": "CONTINUE",
            "HadoopJarStep": {
                "Jar": "command-runner.jar",
                "Properties": [
                    {"Key": "spark.pyspark.python", "Value": "/home/hadoop/project-venv/bin/python"},
                    {"Key": "spark.pyspark.driver.python", "Value": "/home/hadoop/project-venv/bin/python"},
                ],
                "Args": [
                    "spark-submit",
                    "--name", "daily-pyspark-transform",
                    "--py-files", "s3://mystack-example/jobs/shared.zip",
                    "--files", "s3://mystack-example/jobs/settings.json#settings.json",
                    "s3://mystack-example/jobs/main.py",
                    "--input", "s3a://mystack-example/input/",
                    "--output", "s3a://mystack-example/output/",
                ],
            },
        }
    ],
)["StepIds"]
step_id = step_ids[0]
```

Primary application과 `--archives`, `--files`, `--jars`, `--py-files`로 전달한 S3 resource는 Spark를
시작하기 전에 Step work directory로 materialize됩니다. LocalStack host 주소를 command에 넣지 말고
일반 `s3://` 또는 `s3a://` URI를 전달합니다. Mystack은 local Spark process에 설정된 LocalStack S3
endpoint와 path-style S3A 설정을 제공합니다.

<!-- section: observe -->
## Step 추적 및 log 확인

boto3에서 `describe_step(ClusterId=cluster_id, StepId=step_id)`를 polling하거나 `list_steps`,
`cancel_steps`를 사용합니다. [EMR UI](http://localhost:4566/_mystack/ui/emr/)에서는 cluster를 만들고,
Step을 추가하며, 제출한 인자 벡터와 해석된 인자 벡터를 보고, 실시간 stdout/stderr를 따라가고, log를
내려받거나 실행 중인 Step을 취소할 수 있습니다. Add Step dialog에는 한 줄에 하나의 인자를 입력합니다.

`LogUri`를 설정하면 terminal Step은 압축된 controller, syslog, stdout, stderr, synthetic local-driver
application stream을 지정한 S3 prefix 아래에 게시합니다. Path, 재시도, 실행 중에 볼 수 있는 정보는
[LogUri 배치와 복구 계약](protocols/emr-log-layout.ko.md)에서 확인합니다.

<!-- section: prepare -->
## Image 준비 또는 시작 시 cluster provision

Emulator가 시작되기 전에 enterprise certificate, proxy environment variable, 다른 image-wide prerequisite를
준비하려면 검토된 [EMR pre-start 안내](protocols/emr-prestart.ko.md)를 사용합니다. 이것은
`BootstrapActions`와 별개인 image initialization 용도입니다.

Container가 healthy 상태가 되는 즉시 cluster를 사용할 수 있게 하려면 versioned
[startup cluster 파일](protocols/emr-startup-clusters.ko.md)을 제공합니다. 항목은 지원하는
`RunJobFlow` member를 사용하며 boto3로 만든 cluster와 같은 lifecycle을 거칩니다.

<!-- section: sources -->
## 공식 참고 자료

- [Amazon EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [Amazon EMR bootstrap action](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Amazon EMR command-runner.jar](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-commandrunner.html)
- [Amazon EMR Spark Step](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Apache Spark 3.5 application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
