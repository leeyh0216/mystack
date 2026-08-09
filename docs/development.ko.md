<!-- doc-id: development -->
<!-- lang: ko -->

[한국어](development.ko.md) | [English](development.md)

# 개발 환경 설정

<!-- toc:start -->
## 목차

- [사전 요구사항](#사전-요구사항)
- [10분 설정](#10분-설정)
- [Dev Container 설정](#dev-container-설정)
- [설정 우선순위](#설정-우선순위)
- [일상 명령](#일상-명령)
- [변경 위치](#변경-위치)
- [문제 해결](#문제-해결)
<!-- toc:end -->

<!-- section: prerequisites -->
## 사전 요구사항

- Branch push 또는 pull request 생성 시 인증된 Git과 GitHub CLI
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- `.node-version`의 Node.js 24.6.0과 npm(Dev Container 사용 시 별도 설치 불필요)
- [Docker Desktop 또는 Docker Engine과 Compose](https://docs.docker.com/compose/install/)
- 자동 환경 로딩을 위한 선택적 [direnv](https://direnv.net/)
- Glue partition expression ANTLR grammar를 변경할 때만 JDK 17 필요(CI에서 생성 결과 검증)
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

Container에는 Python 3.11, Node.js 24.6.0, digest로 고정한 uv, Docker CLI/Compose, AWS CLI,
GitHub CLI, lock으로 고정한 Python/npm workspace dependency, pre-commit과 editor extension이 준비됩니다. `devcontainer.json`의
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
계약을 따릅니다. Mystack은 management 인증을 제공하지 않으며 실제 AWS credential은 commit하지
않습니다.

<!-- section: commands -->
## 일상 명령

전체 목록은 `make help`가 단일 기준입니다.

```bash
make format
make frontend
make pre-commit
make requirements
make coverage-check
make ghcr-compose-check
make compatibility-check
make antlr-check
make glue-errors-check
make version-show
make version-check
make version-bump PART=patch VERSION_ARGS=--dry-run
make compatibility-case CASE=boto3-botocore-1.43.66-contract
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

`make frontend`는 ESLint, TypeScript project-reference 검사, Vitest component 계약, 두 Vite
production build를 실행합니다. `MYSTACK_FRONTEND_TEST_TIMEOUT_MS`를 양의 millisecond 값으로
지정하면 명시적인 기본 10초 test/hook deadline을 바꿀 수 있습니다. `make pre-commit`은
`uv.lock`과 `package-lock.json`으로 재현되는 repository-local hook을 설치하고 실행합니다.
Python과 React/TypeScript lint/format, 한·영 문서, container requirement lock, botocore model manifest와 생성된
상호운용성·오류 근거의 변경을 commit
전에 차단합니다. Hook lifecycle은 공식 [pre-commit 설치·사용
계약](https://pre-commit.com/#install)을 따릅니다.

Compatibility scenario는 SDK/protocol pytest node ID를 명시적으로 선택하며 생성된 React asset이
필요한 test는 선택하지 않습니다. 일반 Python CI job은 전체 contract module을 실행하기 전에 두
frontend build artifact를 내려받고, browser E2E job은 rendering된 UI 동작을 소유합니다. 따라서 UI
coverage를 줄이지 않으면서 SDK matrix 실패 원인을 protocol code로 한정할 수 있습니다. Artifact
lifecycle은 공식 [GitHub Actions artifact
계약](https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts)을 따릅니다.

`VERSION`은 정식 버전의 단일 원천이고 pre-commit hook이 파생 파일의 불일치를 거부합니다. Release
PR을 열기 전에 [Version과 branch 안내](versioning.ko.md)를 따릅니다. Version 명령 자체는 commit,
push, tag, 게시를 수행하지 않습니다.

<!-- section: locations -->
## 변경 위치

- Wire metadata/공통 JSON 직렬화: `shared/src/mystack/aws_protocol`
- 공통 React primitive와 semantic Tailwind theme token: `ui/src`; 이 package는 EMR/Glue UI를
  import하면 안 됨
- EMR UI application/DTO/API 조립: `emr/ui`; Glue UI application/DTO/API 조립: `glue/ui`;
  service UI는 `@mystack/ui`만 import하며 서로를 import하면 안 됨
- 안정적인 공개 UI forwarding만 담당: `proxy/src/mystack/proxy/forwarder.py`; Proxy는 service
  React code를 package하거나 service DTO를 알면 안 됨
- Proxy route 동작: `proxy/src/mystack/proxy/routing.py`; 새 서비스는 YAML 우선
- Proxy controller capability와 HTTP lifecycle: `proxy/src/mystack/proxy/ports.py`, `runtime.py`
- EMR 상태/동작: `emr/src/mystack/emr/domain`; focused command/query/failure policy/queue driver:
  `emr/src/mystack/emr/application`; Build/Start/Close 소유권: `emr/src/mystack/emr/runtime.py`
- Glue Catalog 동작: `glue/src/mystack/glue/domain`, `application`
- Glue aggregate invariant: `glue/src/mystack/glue/domain/model.py`; focused handler:
  `application/database.py`, `table.py`, `partition.py`, `batch.py`, `initialization.py`
- Inbound use case의 최소 Protocol: 각 service의 `application/use_cases.py`
- AWS operation mapping: 각 service의 `adapters/inbound/aws_{family}.py`; 검토한 구현 inventory:
  `aws_operations.py`; 중복·누락·미분류 차단:
  `shared/src/mystack/aws_protocol/operation_registry.py`
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
- 호환성 실패 log: case ID, 정확한 version, scenario ID, model fingerprint, evidence hash와 수정
  안내. 공식 출처와 명시적 YAML case를 검토한 뒤에만 `make compatibility-generate` 실행
- E2E artifact: 모든 container log
