<!-- doc-id: getting-started -->
<!-- lang: ko -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# Mystack 사용 안내

이 문서는 Mystack을 처음 실행하고 AWS CLI, boto3, AWS SDK for pandas, Docker Compose
application에서 사용하는 과정을 설명합니다. Emulator가 제공하는 API 범위는 [지원 범위](support-scope.ko.md),
Glue 동작을 수정하는 방법은 [확장 SPI 안내](extensions.ko.md)를 참고하세요.

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

Docker Engine과 Compose를 설치하고 private repository를 clone합니다. 최초 image build에는
Spark와 Glue image를 받아야 하므로 12GB 이상의 여유 공간을 권장합니다.

```bash
gh repo clone leeyh0216/mystack
cd mystack
cp .env.example .env
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

Compose file 형식과 `--wait` 동작은 [Docker Compose
문서](https://docs.docker.com/reference/cli/docker/compose/up/)를 기준으로 합니다. 모든
container가 `healthy`가 된 다음 client를 실행하세요.

```bash
aws --endpoint-url http://localhost:4566 glue get-databases
aws --endpoint-url http://localhost:4566 emr list-clusters
aws --endpoint-url http://localhost:4566 s3 ls
```

`.env.example`의 credential은 local emulator용 값입니다. 실제 AWS credential을 `.env`나
repository에 넣지 마세요. 종료할 때 data를 남기려면 `docker compose stop`을 사용합니다.
`make down`은 test용 volume까지 제거하므로 저장 data도 삭제됩니다.

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

<!-- section: overlays -->
## Compose 조합과 설정

| 목적 | 명령에 추가할 file |
| --- | --- |
| 기본 local build와 실행 | `-f compose.yaml` |
| YAML 설정을 rebuild 없이 mount | `-f compose.mount-config.yaml` |
| Glue extension wheel을 읽기 전용 mount | `-f compose.extensions.yaml` |
| 세 SPI의 격리된 repository E2E | `make extension-e2e` |

예를 들어 설정과 Glue extension을 함께 적용하려면 다음과 같이 실행합니다.

```bash
export MYSTACK_CONFIG_FILE="$PWD/config/mystack.yaml"
export MYSTACK_GLUE_EXTENSIONS_DIR="$PWD/extensions"
docker compose \
  -f compose.yaml \
  -f compose.mount-config.yaml \
  -f compose.extensions.yaml \
  up --build --detach --wait
```

Compose는 뒤에 지정한 file을 앞의 설정과 병합합니다. 정확한 규칙은 [Compose file 병합
문서](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)를 참고하세요. 전체
YAML key와 환경변수 우선순위는 [설정 안내](configuration.ko.md)에 있습니다.

<!-- section: verify -->
## 동작 확인과 문제 해결

```bash
make routes
make logs SERVICE=glue
make threads
make tasks
open http://localhost:4566/_mystack/console
```

- `connection refused`: `docker compose ps`에서 Proxy와 dependency health를 확인하세요.
- bind mount 권한 오류: Docker Desktop의 file sharing 권한과 절대 경로를 확인하세요.
- extension이 보이지 않음: `extension.install.*`, `extension.provider.load.*` log를 확인하세요.
- protocol 변경 의심: `make model-check`, `make coverage-check`를 실행하세요.
- test가 멈춤: `config/mystack.yaml`의 `tests.*_timeout_seconds`를 조정하고 thread/task endpoint를
  확인하세요.

관리 endpoint와 log에 관한 자세한 내용은 [관찰성 안내](observability.ko.md)를 참고하세요.

<!-- section: sources -->
## 공식 참고 자료

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Compose file 병합](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint 구성](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [AWS SDK for pandas API](https://aws-sdk-pandas.readthedocs.io/en/stable/api.html)
- [uv Docker 안내](https://docs.astral.sh/uv/guides/integration/docker/)
