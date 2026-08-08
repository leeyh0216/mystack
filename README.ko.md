# Mystack

한국어 | [English](README.md)

Mystack은 Amazon EMR과 AWS Glue Data Catalog를 공식 프로토콜에 맞춰 로컬에서 에뮬레이션하는 프로젝트입니다. LocalStack 앞에서 EMR/Glue 요청을 전용 emulator로 보내고, 다른 AWS 서비스 요청은 body를 변경하지 않고 LocalStack으로 전달합니다.

프로젝트 목표는 다음과 같습니다.

- 공식 wire protocol을 통한 AWS CLI와 AWS SDK 호환
- Amazon EMR 클러스터, bootstrap action, Step 상태 전이 에뮬레이션
- LocalStack S3와 연결된 실제 Spark 3.5.x local mode 실행
- 문서화된 검증·예외 동작을 포함한 Glue Data Catalog 호환
- Spark 3.5.4, Hive 호환 타입, Iceberg 1.7.1 상호운용성
- GHCR에 비공개 게시되는 versioned multi-platform Docker 이미지

Glue Job, JobRun, Crawler는 명시적으로 범위에서 제외합니다. 현재 상태와 목표 범위는 [지원 범위](docs/support-scope.ko.md)와 [호환성 표](docs/compatibility/api-coverage.ko.md)에서 관리합니다.

## 빠른 시작

```bash
cp .env.example .env
direnv allow          # 선택 사항
make bootstrap
make up
aws --endpoint-url http://localhost:4566 glue get-databases
```

`http://localhost:4566/_mystack/console`에서 route, thread stack, asyncio task console을
확인할 수 있습니다. `make up CONFIG=repository/내부/경로.yaml`은 선택한 파일을 local
image에 포함하고, live 개발이나 prebuilt image에는 `compose.mount-config.yaml`로 파일을
read-only mount할 수 있습니다. `MYSTACK__SECTION__KEY`는 배포별 override에만 사용합니다.
자세한 내용은 [설정 가이드](docs/configuration.ko.md)와
[Docker Compose specification](https://docs.docker.com/reference/compose-file/)을 참고하세요.

## 아키텍처

각 서비스는 ports and adapters 구조를 사용합니다. Domain은 FastAPI, boto3, Docker, Spark, subprocess, 저장 구현을 알지 못합니다.

```text
AWS CLI / SDK
      |
      v
  proxy/  --------------------------> LocalStack (S3, ECR, 기타 서비스)
    |  |
    |  +----------------------------> glue/
    +-------------------------------> emr/

domain <- application <- inbound/outbound adapters <- composition root
```

자세한 기준은 [아키텍처](docs/architecture.ko.md), [AWS 프로토콜 분석](docs/protocols/aws-json-1.1.ko.md), [변경 대응 정책](docs/evolution.ko.md)을 참고하세요. 구조 원칙은 AWS의 [Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을 따릅니다.

## 상태

현재 적극적으로 구현 중입니다. EMR은 boto3로 검증한 13개 operation, Glue는 boto3로
검증한 Data Catalog 22개 operation을 제공합니다. 기준선과 구현 기반 UseCase는
[`docs/project`](docs/project)에 있습니다.

동작 기준은 [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data), [AWS Glue 타입 문서](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)입니다.
