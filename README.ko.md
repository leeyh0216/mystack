<!-- doc-id: readme -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# Mystack

Mystack은 Amazon EMR과 AWS Glue Data Catalog를 공식 프로토콜에 맞춰 로컬에서 에뮬레이션하는
Docker 애플리케이션입니다. 사용자는 AWS CLI, boto3와 기존 클라이언트의 endpoint 하나만
`http://localhost:4566`으로 바꾸면 됩니다. Proxy는 EMR/Glue 요청을 전용 emulator로 보내고
다른 AWS 서비스 요청은 본문을 변경하지 않고 LocalStack으로 전달합니다.

현재 제공하는 핵심 경로는 다음과 같습니다.

- 공식 wire protocol을 통한 AWS CLI와 AWS SDK 호환
- Amazon EMR 클러스터, bootstrap action, Step 상태 전이 에뮬레이션
- LocalStack S3와 연결된 실제 Spark 3.5.x local mode 실행
- pause/resume/download, 재시작 복구, S3 게시를 지원하는 EMR Step stdout/stderr
- 문서화된 검증·예외 동작을 포함한 Glue Data Catalog 호환
- Spark 3.5.4, Hive 호환 타입, Iceberg 1.7.1 상호운용성
- AWS SDK for pandas 3.17.0 기반 partitioned Parquet와 Glue Catalog 왕복
- Docker Compose 기반의 재현 가능한 local 실행 환경

Glue Job, JobRun, Crawler는 명시적으로 범위에서 제외합니다. “일부 경로 E2E 통과”를 라이브러리
전체 지원으로 해석하지 않습니다. 정확한 범위는 [지원 범위](docs/support-scope.ko.md),
[Client 호환성 표](docs/compatibility/client-matrix.ko.md),
[API coverage](docs/compatibility/api-coverage.ko.md)에서 확인하세요.

<!-- section: quick-start -->
## 빠른 시작

일반적인 실행 경로는 public 게시 image를 익명으로 pull하며 repository를 clone하거나 build하지
않습니다. Docker Engine과 Compose를 설치하고 image와 같은 public Git tag에서 Compose file을
받으세요. Package/release page에서 실제 semantic tag를 선택합니다. Public
GHCR package는 registry token이나 registry 로그인이 필요하지 않습니다. GitHub 공식 [Package
권한 안내](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages)를
참고하세요.

```bash
export MYSTACK_IMAGE_TAG=v0.1.0  # 실제 게시 tag로 교체
mkdir mystack-runtime && cd mystack-runtime
curl --fail --location --output compose.ghcr.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.ghcr.yaml"

docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
curl --fail http://localhost:4566/_mystack/health
```

`http://localhost:4566/_mystack/console`에서 EMR cluster 생성·운영, Step 제출·추적, live log
follow/pause/download,
Glue database/table/schema/partition 탐색, route, thread stack, asyncio task 확인을 할 수
있습니다. Docker Compose 조합, boto3와 AWS SDK for pandas 연결, upgrade, rollback,
문제 해결과 정리는 [상세 사용 안내](docs/getting-started.ko.md)부터 읽어보세요. Source build는 일반
사용 경로가 아니며 [개발 환경 안내](docs/development.ko.md)에 있습니다.

<!-- section: user-paths -->
## 원하는 작업부터 찾기

| 하려는 작업 | 읽을 문서 |
| --- | --- |
| Docker Compose로 처음 실행 | [상세 사용 안내](docs/getting-started.ko.md) |
| AWS CLI, boto3, AWS SDK for pandas 연결 | [상세 사용 안내의 client 절차](docs/getting-started.ko.md) |
| 지원하는 EMR/Glue API와 오류 확인 | [지원 범위](docs/support-scope.ko.md), [API coverage](docs/compatibility/api-coverage.ko.md) |
| Spark Glue Hive/Iceberg와 라이브러리 검증 범위 확인 | [Client 호환성 표](docs/compatibility/client-matrix.ko.md) |
| YAML, timeout, port, Docker 설정 변경 | [설정 안내](docs/configuration.ko.md) |
| EMR 시작 전에 enterprise CA 또는 proxy 설치 | [EMR pre-start 안내](docs/protocols/emr-prestart.ko.md) |
| EMR 운영, Glue 탐색, 진단 확인 | [관리 Console 안내](docs/console.ko.md) |

사용자 문서 전체의 권장 순서는 [사용자 안내](docs/index.ko.md)에 있습니다.

<!-- section: support -->
## 현재 지원 수준

현재 적극적으로 구현 중입니다. EMR은 boto3로 검증한 13개 operation, Glue는 boto3로
검증한 Data Catalog 22개 operation을 제공합니다. Spark 3.5.4 Hive/Iceberg와 AWS SDK for
pandas 3.17.0은 문서에 적힌 세로 경로만 E2E로 검증합니다. Athena, Glue Job/JobRun/Crawler,
운영 IAM, YARN/HDFS 환경은 현재 지원하지 않습니다.

<!-- section: maintainers -->
## 구현하거나 관리하는 분

아키텍처, 프로토콜, 개발 환경, 시험, CI, 배포와 상위 의존성 변경 대응 문서는 사용자 안내와
분리한 [유지보수 안내](docs/maintainers.ko.md)에 있습니다. 기여를 시작할 때는 이 안내와
[기여 가이드](CONTRIBUTING.ko.md)를 따르세요.

동작 기준은 [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data), [AWS Glue 타입 문서](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)입니다.
