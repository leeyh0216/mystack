<!-- doc-id: getting-started -->
<!-- lang: ko -->

[한국어](getting-started.ko.md) | [English](getting-started.md)

# 시작하기

<!-- toc:start -->
## 목차

- [Docker Compose 시작](#docker-compose-시작)
- [AWS client 연결](#aws-client-연결)
- [작업별 다음 문서](#작업별-다음-문서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

게시된 Docker Compose stack을 시작하고 동작을 확인한 뒤 AWS client를 로컬 endpoint에 연결합니다.

<!-- section: start -->
## Docker Compose 시작

Docker Engine과 Docker Compose를 설치한 뒤 게시된 version을 선택합니다.

```bash
export MYSTACK_IMAGE_TAG=<게시된-version>
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

Host endpoint는 `http://localhost:4566`입니다. 같은 Compose network의 container에서는
`http://proxy:8080`을 사용합니다.

<!-- section: clients -->
## AWS client 연결

각 AWS service client에 같은 endpoint와 로컬 개발용 credential을 사용합니다.

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_EC2_METADATA_DISABLED=true

aws --endpoint-url "$AWS_ENDPOINT_URL" glue get-databases
aws --endpoint-url "$AWS_ENDPOINT_URL" emr list-clusters
```

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

다른 Docker Compose project의 application은 `http://host.docker.internal:4566`을 사용하고,
Linux에서는 필요한 경우 Docker `host-gateway` mapping을 추가합니다.

<!-- section: next -->
## 작업별 다음 문서

- [Glue Data Catalog](glue.ko.md): boto3, AWS SDK for pandas, Spark Hive, Iceberg.
- [Amazon EMR](emr.ko.md): cluster, bootstrap action, Spark/PySpark Step, log.
- [설정](configuration.ko.md): port, timeout, path, mount configuration.
- [운영](operations.ko.md): 관리 UI, 진단, upgrade, cleanup.

<!-- section: sources -->
## 공식 참고 자료

- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Docker host-gateway](https://docs.docker.com/reference/cli/docker/container/run/#add-entries-to-container-hosts-file---add-host)
- [AWS SDK endpoint 설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
