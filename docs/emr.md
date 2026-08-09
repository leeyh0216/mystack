<!-- doc-id: emr-guide -->
<!-- lang: en -->

[한국어](emr.ko.md) | [English](emr.md)

# Amazon EMR

<!-- toc:start -->
## Contents

- [Create a cluster](#create-a-cluster)
- [Prepare a cluster with a bootstrap action](#prepare-a-cluster-with-a-bootstrap-action)
- [Submit a full Spark or PySpark argument vector](#submit-a-full-spark-or-pyspark-argument-vector)
- [Track Steps and inspect logs](#track-steps-and-inspect-logs)
- [Prepare the image or provision clusters at startup](#prepare-the-image-or-provision-clusters-at-startup)
- [Official sources](#official-sources)
<!-- toc:end -->

Use this guide to create a local EMR cluster, prepare it with a bootstrap action, and run a
Spark or PySpark application whose code and data are in LocalStack S3.

For the request-to-Spark-process and LogUri flow, see the optional [EMR execution architecture](emr-execution-architecture.md).

<!-- section: cluster -->
## Create a cluster

Use the same host endpoint as other AWS clients. `LogUri` is optional, but its bucket must already
exist when you want terminal Step logs in LocalStack S3. The release label below is the default
configured profile; choose a label from your [configuration](configuration.md) when it differs.

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

`KeepJobFlowAliveWhenNoSteps=True` leaves the cluster ready for later `AddJobFlowSteps` calls. The
emulator runs Spark 3.5 in local mode inside its EMR container; instance counts model the EMR
request but do not create EC2 or YARN workers.

<!-- section: bootstrap -->
## Prepare a cluster with a bootstrap action

Put the script in LocalStack S3 and reference it through `BootstrapActions` in `RunJobFlow`.
Mystack downloads the script before running it as `hadoop`. A bootstrap action can create a
virtual environment; use `sudo` only for a deliberate root-level change.

```bash
#!/usr/bin/env bash
set -euo pipefail

venv=/home/hadoop/project-venv
python3.11 -m venv "$venv"
"$venv/bin/python" -m pip --version
# Install application dependencies here when your environment makes them available.
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

Wait until `describe_cluster(ClusterId=cluster_id)` reports `WAITING` before adding a Step. A
non-zero bootstrap exit makes cluster startup fail.

<!-- section: submit -->
## Submit a full Spark or PySpark argument vector

Submit a Spark Step through `command-runner.jar`. `Args` is an argument vector, not a shell string:
the first item is `spark-submit`, options precede the application, and each following item is an
application argument. A PySpark workload is a Python application submitted by `spark-submit`, not
an interactive `pyspark` shell.

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

The primary application and S3 resources passed through `--archives`, `--files`, `--jars`, or
`--py-files` are materialized into the Step work directory before Spark starts. Pass normal
`s3://` or `s3a://` URIs; do not put the LocalStack host address in the command. Mystack supplies
the configured LocalStack S3 endpoint and path-style S3A settings to the local Spark process.

<!-- section: observe -->
## Track Steps and inspect logs

Poll `describe_step(ClusterId=cluster_id, StepId=step_id)` or use `list_steps` and `cancel_steps`
from boto3. The [EMR UI](http://localhost:4566/_mystack/ui/emr/) can create a cluster, add a Step,
show the submitted and resolved argument vectors, follow live stdout/stderr, download logs, and
cancel a running Step. In its Add Step dialog, enter one argument per line.

With `LogUri`, terminal Steps publish compressed controller, syslog, stdout, stderr, and synthetic
local-driver application streams below the configured S3 prefix. The detailed
[LogUri layout and recovery contract](protocols/emr-log-layout.md) describes paths, retries, and
what is available while a Step is running.

<!-- section: prepare -->
## Prepare the image or provision clusters at startup

For enterprise certificates, proxy environment variables, or other image-wide prerequisites before
the emulator starts, use the reviewed [EMR pre-start guide](protocols/emr-prestart.md). It is
separate from `BootstrapActions` and is intended for image initialization.

To make clusters available as soon as the container becomes healthy, provide the versioned
[startup cluster file](protocols/emr-startup-clusters.md). Its entries use supported `RunJobFlow`
members and enter the same lifecycle as boto3-created clusters.

<!-- section: sources -->
## Official sources

- [Amazon EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [Amazon EMR bootstrap actions](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Amazon EMR command-runner.jar](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-commandrunner.html)
- [Amazon EMR Spark Steps](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Apache Spark 3.5 application submission](https://spark.apache.org/docs/3.5.4/submitting-applications.html)
