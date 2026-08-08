<!-- doc-id: development -->
<!-- lang: ko -->

[한국어](development.ko.md) | [English](development.md)

# 개발 환경 설정

<!-- section: prerequisites -->
## 사전 요구사항

- Private repository 접근 권한이 있는 Git과 GitHub CLI
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker Desktop 또는 Docker Engine과 Compose](https://docs.docker.com/compose/install/)
- 자동 환경 로딩을 위한 선택적 [direnv](https://direnv.net/)
- Spark/Glue 호환 이미지와 테스트 데이터를 위한 12GB 이상 여유 공간

<!-- section: setup -->
## 10분 설정

```bash
gh repo clone leeyh0216/mystack
cd mystack
cp .env.example .env
direnv allow                 # 선택
make bootstrap
make pre-commit
make up
```

Public endpoint와 적용 route를 확인합니다.

```bash
curl http://localhost:4566/_mystack/health
make routes
AWS_ENDPOINT_URL=http://localhost:4566 aws s3 ls
```

AWS endpoint 환경변수는 [공식 SDK endpoint 설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)을 따릅니다.

<!-- section: devcontainer -->
## Dev Container 설정

Host에 Docker와 VS Code Dev Containers extension이 있다면 별도 Python·uv·AWS CLI 설치 없이
시작할 수 있습니다. Local clone을 연 다음 `Dev Containers: Reopen in Container`를 실행하세요.
`.devcontainer/devcontainer.json`은 workspace를 Host와 같은 절대 경로에 mount하고 Host Docker
daemon을 사용합니다. 생성이 끝나면 `make up`과 `make test`를 그대로 실행할 수 있습니다.

Container에는 Python 3.11, digest로 고정한 uv, Docker CLI/Compose, AWS CLI, GitHub CLI,
locked workspace dependency, pre-commit과 editor extension이 준비됩니다. `devcontainer.json`의
feature 버전과 `devcontainer-lock.json`의 resolved digest를 함께 commit합니다. CI는
[공식 Dev Container CLI](https://github.com/devcontainers/cli)의 `--frozen-lockfile`로 같은 image를
build합니다.

`postCreateCommand`가 끝난 다음 다음 명령으로 환경을 검증합니다.

```bash
make test
make up
curl --fail "$AWS_ENDPOINT_URL/_mystack/health"
aws --endpoint-url "$AWS_ENDPOINT_URL" glue get-databases
```

Dev Container는 [Docker-outside-of-Docker
feature](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker)를 사용합니다.
`Clone Repository in Container Volume` 대신 Host의 local clone을 `Reopen in Container`로 여세요.
Compose의 설정 bind mount를 Host daemon이 해석하므로 Host와 container의 workspace
절대 경로가 같아야 합니다. Apple Silicon에서는 두 환경의 architecture도 같게 유지합니다. 이
구성은 공식 [Dev Container 생성
안내](https://code.visualstudio.com/docs/devcontainers/create-dev-container)를 따릅니다.

<!-- section: precedence -->
## 설정 우선순위

1. executable `--config`, `MYSTACK_CONFIG_FILE`, 기본값 순으로 YAML file 선택
2. 범용 `MYSTACK__SECTION__KEY` 환경변수로 nested value override
3. executable `--host`, `--port`로 process listener만 마지막 override

```bash
export MYSTACK_CONFIG_FILE=config/mystack.yaml
export MYSTACK__LOGGING__LEVEL=DEBUG
export MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600
mystack-proxy --config "$MYSTACK_CONFIG_FILE"
```

`make up CONFIG=...`은 repository 안의 YAML을 build 시 image에 포함합니다. Read-only live
mount가 필요하면 [설정 가이드](configuration.ko.md)에 따라 `-f compose.mount-config.yaml`을
추가합니다. 두 방식 모두 [Docker Compose configs](https://docs.docker.com/reference/compose-file/configs/)
계약을 따릅니다. 공유 환경 management token과 실제 AWS credential은 commit하지 않습니다.

<!-- section: commands -->
## 일상 명령

전체 목록은 `make help`가 단일 기준입니다.

```bash
make format
make pre-commit
make requirements
make coverage-check
make package-check
make architecture-check
make test
make contract
make e2e
make logs SERVICE=emr
make threads
make down
```

Timeout은 YAML `tests` section에서 읽습니다. Service process/bootstrap timeout은 별도이며 가능한 경우 바깥 test timeout보다 먼저 adapter가 hung subprocess를 종료합니다.

`make pre-commit`은 `uv.lock`으로 재현되는 repository-local hook을 설치하고 실행합니다.
Lint/format, 한·영 문서, container requirement lock, botocore model manifest drift를 commit
전에 차단합니다. Hook lifecycle은 공식 [pre-commit 설치·사용
계약](https://pre-commit.com/#install)을 따릅니다.

<!-- section: locations -->
## 변경 위치

- Wire metadata/공통 JSON 직렬화: `shared/src/mystack/aws_protocol`
- Proxy route 동작: `proxy/src/mystack/proxy`; 새 서비스는 YAML 우선
- EMR 상태/동작: `emr/src/mystack/emr/domain`, `application`
- Glue Catalog 동작: `glue/src/mystack/glue/domain`, `application`
- Inbound use case의 최소 Protocol: 각 service의 `application/use_cases.py`
- S3, process, database, FastAPI: 각 서비스 `adapters`
- Dependency wiring: composition root만

네 distribution은 `mystack/__init__.py` 없이 `mystack.aws_protocol`, `mystack.proxy`,
`mystack.emr`, `mystack.glue`를 각각 제공합니다. Module을 옮기거나 build backend를 바꾸면
`make package-check`를 실행합니다.

의존 방향은 [AWS Hexagonal architecture 모델](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)에 맞춰 CI가 검사합니다. Module을 옮기거나
import를 바꾼 뒤 `make architecture-check`를 실행하세요. 실패 결과에서 source, imported module,
위반 rule, 수정 안내를 확인할 수 있습니다.

<!-- section: troubleshooting -->
## 문제 해결

- `make bootstrap`: 도구, 문서, model drift, fast test 문제 진단
- `make logs SERVICE=proxy`: JSON 경계 event 확인
- `make threads`, `make tasks`: frame locals 없는 live stack 수집
- `model-drift-report.json`: 변경 operation과 수정 위치
- `api-coverage-drift-report.json`: 미분류·삭제·데이터 구조 변경·잘못 분류된 작업과 수정 경계
- E2E artifact: 모든 container log
