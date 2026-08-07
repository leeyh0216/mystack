# 설정과 재현 가능한 컨테이너

한국어 | [English](configuration.md)

Mystack의 runtime 동작은 versioned `config/mystack.yaml`에 둡니다. Service endpoint,
credential, release mapping, process deadline, Spark submit parsing table, route 등록, test
deadline의 fallback을 application 코드에 두지 않습니다. Docker 공식 지침이 구분하는
build argument, runtime environment variable, read-only config, secret을 각 경계에 맞게
사용합니다. [Docker build 변수](https://docs.docker.com/build/building/variables/),
[Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/),
[Compose configs](https://docs.docker.com/reference/compose-file/configs/)를 참고하세요.

## 적용 순서

1. `--config PATH`, `MYSTACK_CONFIG_FILE`, `config/mystack.yaml` 순으로 base file을 선택합니다.
2. 모든 `MYSTACK__SECTION__KEY` 환경변수가 해당 nested YAML 값을 대체합니다. 값은 YAML로
   parse하므로 숫자, boolean, list, mapping, `null` 타입을 보존합니다.
3. Process 전용 `--host`, `--port`가 해당 service listener를 마지막으로 override합니다.

```bash
MYSTACK_CONFIG_FILE=config/mystack.yaml \
MYSTACK__LOGGING__LEVEL=DEBUG \
MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600 \
mystack-proxy
```

민감한 override path는 로그에서 가립니다. Production credential과 management token을
commit된 YAML에 넣지 말고 배포 시 주입합니다. Docker의 일반 환경 설정과
[secret](https://docs.docker.com/compose/how-tos/use-secrets/) 구분을 따르세요.

## Docker 실행 방식

기본 `make up CONFIG=config/mystack.yaml`은 `CONFIG`를 `MYSTACK_CONFIG_SOURCE` build
argument로 전달하고 repository 안의 해당 파일을 `/etc/mystack/mystack.yaml`에 복사합니다.
Image와 설정이 불변이며 bind mount가 제한된 Docker host에서도 동작합니다. Source file은
Docker build context 안에 있어야 합니다.

개발 중 즉시 파일을 바꾸거나 prebuilt ECR image를 사용할 때는 read-only mount overlay를
사용합니다.

```bash
MYSTACK_CONFIG_FILE=./config/mystack.yaml \
docker compose -f compose.yaml -f compose.mount-config.yaml up --detach --wait
```

Mounted file을 수정한 뒤 해당 container를 재시작합니다. 설정은 process 시작 시 한 번만
읽으며 일부 값만 적용된 hot reload는 하지 않습니다.

## 주요 section

| 경로 | 책임 |
| --- | --- |
| `logging` | 구조화 log level과 format 계약 |
| `management.diagnostics` | thread/task stack 활성화, bearer token, 최대 깊이 |
| `proxy` | listener, fallback, outbound timeout, 확장 가능한 route registry |
| `localstack` | S3 endpoint, region, account, local credential, path-style 동작 |
| `emr` | 작업 저장소, deadline, process 정책, release profile, operation limit |
| `glue` | durable catalog state, catalog ID, paging, runtime profile |
| `runtime_profiles` | Spark command/master/package/conf/parser option과 Glue version |
| `tests` | Unit/contract/E2E/Compose deadline과 black-box client/runtime 설정 |

새 설정은 YAML에 추가하고 해당 composition-root configuration adapter에서 typed value로
mapping하며 설정 test와 한·영 문서를 함께 추가합니다. 안쪽 Domain/Application module은
file이나 environment를 읽지 않고 typed policy/value object만 받습니다.

Environment override를 적용한 뒤 모든 process가 전체 document를 package에 포함된
[`mystack.schema.json`](../shared/src/mystack_aws_protocol/mystack.schema.json)으로 검증합니다.
Unknown key, 누락 member, 잘못된 URL/account ID/port, 0 이하 deadline은 시작 전에 정확한
dotted path와 함께 실패합니다. Schema는 공식
[JSON Schema 2020-12 specification](https://json-schema.org/draft/2020-12/json-schema-core)을
사용합니다.

## 재현 가능한 build 입력

- `uv.lock`: 개발 dependency lock
- `requirements/{proxy,emr,glue}.txt`: `make requirements`가 생성하는 hash lock
- CI의 `scripts/export_requirements.py --check`: lockfile/export drift 차단
- 기본 container base: immutable multi-architecture digest; 의도적 변경은 Compose 변수 사용
- Spark archive: version argument와 공개 SHA-512 검증
- Runtime profile과 실제 Spark/Hive/Iceberg E2E: image/config 버전 불일치 탐지

Export 방식은 공식 [uv export interface](https://docs.astral.sh/uv/reference/cli/#uv-export)를
따릅니다.
