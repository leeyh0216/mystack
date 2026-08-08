<!-- doc-id: getting-started -->
<!-- lang: ko -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Mystack 사용 안내

이 문서는 Mystack을 처음 실행하고 AWS CLI, boto3, AWS SDK for pandas, Docker Compose
application에서 사용하는 과정을 설명합니다. Emulator가 제공하는 API와 명시적 제외 범위는
[지원 범위](support-scope.ko.md)를 참고하세요.

<!-- section: choose -->
## 실행 환경 선택

| 환경 | 권장 대상 | AWS endpoint |
| --- | --- | --- |
| Host의 Docker Compose | Mystack을 사용하는 application 개발자 | `http://localhost:4566` |
| 같은 Compose network의 container | Mystack과 함께 실행하는 service | `http://proxy:8080` |

Mystack의 공개 endpoint는 Proxy 하나입니다. 요청의 `X-Amz-Target`, SigV4 signing service,
host 정보를 보고 EMR, Glue, LocalStack으로 전달합니다. AWS SDK의 endpoint 설정은 공식
[AWS SDK endpoint 구성](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)을
따릅니다.

<!-- section: compose -->
## Docker Compose로 시작하기

Docker Engine과 Compose를 설치하고 private repository의 Compose file을 받을 때만 GitHub CLI를
인증합니다. Source clone, Python 환경, Java 설치, local image build, registry token, registry
로그인은 필요하지 않습니다. Public image는 익명으로 pull합니다. 세 `mystack-*` package에 모두
존재하는 tag를 선택하세요. `latest`는 의도적으로 제공하지 않습니다.

```bash
export MYSTACK_IMAGE_TAG=v0.1.0  # 실제 게시 tag로 교체
mkdir mystack-runtime && cd mystack-runtime
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.ghcr.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.ghcr.yaml
printf 'MYSTACK_IMAGE_TAG=%s\n' "$MYSTACK_IMAGE_TAG" > .env

docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

GitHub [Package 권한 안내](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages)에
따르면 public container package는 익명으로 pull할 수 있습니다. `gh auth`는 private repository에서
file 하나를 받는 권한만 별도로 제공하며 image pull에는 사용하지 않습니다. 해당 repository
credential을 `.env`에 저장하지 마세요.

Image 전용 Compose file에는 `build` key가 없습니다. Compose의 [필수 변수
치환](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)으로 명시적
tag를 요구하고 해당 release에 포함된 설정을 사용합니다. 네 container가 모두 `healthy`가 된 뒤
client를 실행하세요.

```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 glue get-databases
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 emr list-clusters
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:4566 s3 ls
```

이 값은 local emulator용이며 실제 AWS credential이 아닙니다. 실제 AWS credential을 이 runtime
directory에 넣지 마세요.

<!-- section: clients -->
## boto3와 application 연결하기

boto3 client마다 같은 endpoint를 지정할 수 있습니다.

```python
import boto3

glue = boto3.client(
    "glue",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
print(glue.get_databases())
```

Host에서 실행하는 application에는 다음 환경변수를 전달합니다.

```dotenv
AWS_ENDPOINT_URL=http://localhost:4566
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_EC2_METADATA_DISABLED=true
```

Mystack과 application이 같은 Compose network를 사용하면 `AWS_ENDPOINT_URL=http://proxy:8080`을
지정합니다. 별도 container에서 host port로 접근할 때 Docker Desktop은
`http://host.docker.internal:4566`을 사용합니다. Linux에서는 application service에 다음 host
mapping을 추가할 수 있습니다.

```yaml
services:
  my-application:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      AWS_ENDPOINT_URL: http://host.docker.internal:4566
```

이 mapping은 Docker의 [host-gateway 특별
값](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)을
사용합니다.

AWS SDK for pandas(`awswrangler`)는 Glue와 S3의 service별 endpoint를 같은 Proxy로 지정합니다.
아래 예제는 bucket과 database를 만든 뒤 partitioned Parquet data와 Glue table을 함께 등록하고
다시 읽습니다.

```bash
export AWS_ENDPOINT_URL_GLUE=http://localhost:4566
export AWS_ENDPOINT_URL_S3=http://localhost:4566
```

```python
import awswrangler as wr
import boto3
import pandas as pd

boto3.client("s3").create_bucket(Bucket="mystack-example")
wr.catalog.create_database(name="demo")
wr.s3.to_parquet(
    df=pd.DataFrame({"id": [1, 2], "day": ["2026-08-08", "2026-08-09"]}),
    path="s3://mystack-example/events/",
    dataset=True,
    database="demo",
    table="events",
    partition_cols=["day"],
)
print(wr.s3.read_parquet(path="s3://mystack-example/events/", dataset=True))
```

현재 검증한 함수와 제외한 service는 [Client 호환성 표](compatibility/client-matrix.ko.md)에
있습니다. 특히 `wr.athena.*`는 현재 지원 범위가 아닙니다.

<!-- section: emr-runtime -->
## EMR bootstrap과 Spark application 실행

EMR container, bootstrap script와 Spark subprocess는 `/home/hadoop`을 home으로 사용하는
`hadoop` 사용자로 실행합니다. 이는 [bootstrap action이 Hadoop 사용자로 실행되고 root 작업에는
`sudo`를 사용](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)하는
Amazon EMR 동작을 따릅니다. 격리된 emulator container에서는 이 사용자에게 passwordless
`sudo`를 제공합니다.

Bootstrap action은 LocalStack S3에서 내려받아 순서대로 실행하며 모두 끝난 뒤 cluster가 Step을
받습니다. Bootstrap에서 만든 file과 virtualenv는 같은 container의 뒤 Step에서 볼 수 있습니다.
다만 process 사이에는 shell 상태가 전달되지 않습니다. Bootstrap script 안에서 `source`로
virtualenv를 활성화해도 뒤 Spark process에는 활성화되지 않으므로 Step에 interpreter를 명시합니다.

```python
step = {
    "Name": "pyspark-with-bootstrap-venv",
    "HadoopJarStep": {
        "Jar": "command-runner.jar",
        "Properties": [
            {"Key": "spark.pyspark.python", "Value": "/home/hadoop/venv/bin/python"},
            {"Key": "spark.pyspark.driver.python", "Value": "/home/hadoop/venv/bin/python"},
        ],
        "Args": ["spark-submit", "s3://my-bucket/jobs/main.py"],
    },
}
```

주 Python/JAR application은 `spark-submit` 전에 `s3://`, `s3a://`, `s3n://`, `file://`에서 Step
work directory로 복사합니다. `--py-files`, `--files`, `--jars`, `--archives`에 쉼표로 지정한
remote resource도 local로 materialize하며 archive/file URI fragment는 보존합니다. 그 밖의 Spark
option은 그대로 전달합니다. 이는 Spark가 주 entrypoint를 remote에서 해석하는 데 기대지 않고 공식
[S3 application location 계약](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)을
구현합니다.

`run_job_flow`에 `LogUri="s3://이미-존재하는-bucket/prefix/"`를 지정하면 gzip Step
`controller`/`syslog`/`stdout`/`stderr` object와 local Spark driver stream을 보관합니다. Console
Logs tab에서 게시 상태가 `published`, `failed`, `skipped`인지와 전체 object key를 확인할 수
있습니다. 복사해 쓸 수 있는 boto3 사용법, 정확한 경로, 실패 의미와 local-mode/YARN 차이는
[EMR LogUri 배치](protocols/emr-log-layout.ko.md)를 참고하세요.

<!-- section: overlays -->
## Compose 조합과 설정

| 목적 | 명령에 추가할 file |
| --- | --- |
| 게시 image와 포함된 기본 설정으로 실행 | `-f compose.ghcr.yaml` |
| 검토한 YAML 설정을 read-only mount | `-f compose.mount-config.yaml` 추가 |
| Mystack source build 또는 변경 | 이 사용자 경로가 아닌 [개발 환경 안내](development.ko.md) 사용 |

설정을 바꾸기 전에 같은 Git tag에서 설정과 overlay를 받습니다.

```bash
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/config/mystack.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > mystack.yaml
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.mount-config.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.mount-config.yaml
export MYSTACK_CONFIG_FILE="$PWD/mystack.yaml"
docker compose \
  -f compose.ghcr.yaml \
  -f compose.mount-config.yaml \
  up --detach --wait --wait-timeout 300
```

Compose는 뒤에 지정한 file을 앞의 설정과 병합합니다. 정확한 규칙은 [Compose file 병합
문서](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)를 참고하세요. 전체
YAML key와 환경변수 우선순위는 [설정 안내](configuration.ko.md)에 있습니다.

<!-- section: lifecycle -->
## Upgrade, rollback과 정리

Proxy, EMR, Glue에 모두 존재하는 tag로만 upgrade합니다. 같은 Git tag의 Compose file로 교체하고
`.env`를 갱신한 뒤 먼저 pull합니다. Compose는 변경된 container를 다시 만들고 named volume은
보존합니다.

```bash
export MYSTACK_IMAGE_TAG=v0.2.0
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.ghcr.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.ghcr.yaml
printf 'MYSTACK_IMAGE_TAG=%s\n' "$MYSTACK_IMAGE_TAG" > .env
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
```

Rollback은 이전에 검증한 tag로 같은 절차를 실행합니다. 배포 identity를 엄격하게 고정하려면 release
artifact의 세 `ghcr.io/...@sha256:...` 전체 값을 `MYSTACK_PROXY_IMAGE`, `MYSTACK_EMR_IMAGE`,
`MYSTACK_GLUE_IMAGE`로 지정하세요. 이 값은 공통 tag보다 우선합니다. Compose가 모든 fallback을
검증할 수 있도록 `.env`의 필수 `MYSTACK_IMAGE_TAG` entry는 유지하세요.

```bash
docker compose -f compose.ghcr.yaml stop                  # container와 data 보존
docker compose -f compose.ghcr.yaml down                  # container 제거, named volume 보존
docker compose -f compose.ghcr.yaml down --volumes        # emulator state 영구 제거
```

마지막 명령은 EMR, Glue, LocalStack data를 삭제합니다. Mystack public image는 저장된 Docker
registry credential을 추가하거나 변경하지 않습니다.

<!-- section: verify -->
## 동작 확인과 문제 해결

```bash
docker compose -f compose.ghcr.yaml ps
docker compose -f compose.ghcr.yaml logs --tail 200 proxy glue emr
curl --fail http://localhost:4566/_mystack/routes
curl --fail http://localhost:4566/_mystack/diagnostics/threads
curl --fail http://localhost:4566/_mystack/diagnostics/tasks
open http://localhost:4566/_mystack/console
```

- `unauthorized` 또는 `denied`: package 소유자가 세 package를 모두 public으로 전환했는지와 image
  이름이 정확한지 확인하세요. Consumer token을 우회 방법으로 추가하지 마세요.
- `manifest unknown`: 선택한 tag가 세 package에 모두 있어야 하며 `latest`는 없습니다.
- `connection refused`: `docker compose ps`에서 Proxy와 dependency health를 확인하세요.
- bind mount 권한 오류: Docker Desktop의 file sharing 권한과 절대 경로를 확인하세요.
- 작업이 멈춤: service deadline을 바꾸기 전에 thread/task endpoint와 component log를 확인하세요.
- protocol 또는 client 불일치 의심: 선택한 version과 생성된 [Client 호환성
  근거](compatibility/client-matrix.ko.generated.md)를 비교하세요.

관리 endpoint와 log에 관한 자세한 내용은 [관찰성 안내](observability.ko.md)를 참고하세요.

<!-- section: sources -->
## 공식 참고 자료

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Compose 변수 치환](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Compose file 병합](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint 구성](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [uv Docker 안내](https://docs.astral.sh/uv/guides/integration/docker/)
