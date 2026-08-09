<!-- doc-id: readme -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# Mystack

<!-- toc:start -->
## 목차

- [Docker Compose로 시작하기](#docker-compose로-시작하기)
- [Mystack 사용하기](#mystack-사용하기)
- [Contributors](#contributors)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

Mystack은 Docker Compose로 로컬 Amazon EMR과 AWS Glue Data Catalog 환경을 실행합니다. AWS client,
Spark, LocalStack S3를 사용하는 애플리케이션과 데이터 파이프라인 개발에 사용할 수 있습니다.

<!-- section: start -->
## Docker Compose로 시작하기

게시된 image version을 선택하고 같은 version의 Compose file을 받은 뒤 stack을 시작합니다.

```bash
export MYSTACK_IMAGE_TAG=<게시된-version>
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

다음 작업은 [문서 허브](docs/index.ko.md)에서 선택합니다.

<!-- section: use -->
## Mystack 사용하기

| 하려는 일 | 시작 문서 |
| --- | --- |
| Docker Compose를 시작하고 AWS client 연결 | [시작 안내](docs/getting-started.ko.md) |
| boto3, AWS SDK for pandas, Spark Hive, Iceberg로 Glue Data Catalog 사용 | [Glue 안내](docs/glue.ko.md) |
| EMR cluster 생성, bootstrap action 실행, Spark Step 제출 | [EMR 안내](docs/emr.ko.md) |
| Port, timeout, storage, runtime 설정 변경 | [설정](docs/configuration.ko.md) |
| 지원하는 client 경로 확인 | [호환성](docs/compatibility/client-matrix.ko.md) |
| EMR·Glue 관리 UI와 진단 사용 | [운영](docs/operations.ko.md) |

<!-- section: contribute -->
## Contributors

Architecture, protocol reference, 개발 환경, test, CI, release 운영은
[Contributors 안내](docs/maintainers.ko.md)에 있습니다. 저장소 변경 전에는
[CONTRIBUTING.ko.md](CONTRIBUTING.ko.md)를 읽어 주세요.

<!-- section: sources -->
## 공식 참고 자료

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Docker Compose reference](https://docs.docker.com/reference/compose-file/)
