<!-- doc-id: configuration -->
<!-- lang: ko -->

[한국어](configuration.ko.md) | [English](configuration.md)

# 설정과 재현 가능한 컨테이너

<!-- toc:start -->
## 목차

- [적용 순서](#적용-순서)
- [Docker 실행 방식](#docker-실행-방식)
- [주요 section](#주요-section)
- [재현 가능한 build 입력](#재현-가능한-build-입력)
<!-- toc:end -->

Mystack의 실행 환경 동작은 versioned `config/runtime/mystack.yaml`에 둡니다. Service 엔드포인트,
credential, release mapping, process deadline, Spark submit parsing table, route 등록, 테스트
deadline의 fallback을 application 코드에 두지 않습니다. Docker 공식 지침이 구분하는
build argument, 실행 환경 environment variable, read-only config, secret을 각 경계에 맞게
사용합니다. [Docker build 변수](https://docs.docker.com/build/building/variables/),
[Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/),
[Compose configs](https://docs.docker.com/reference/compose-file/configs/)를 참고하세요.

<!-- section: resolution -->
## 적용 순서

1. `--config PATH`, `MYSTACK_CONFIG_FILE`, `config/runtime/mystack.yaml` 순으로 base 파일을 선택합니다.
2. 모든 `MYSTACK__SECTION__KEY` 환경변수가 해당 nested YAML 값을 대체합니다. 값은 YAML로
   parse하므로 숫자, boolean, list, mapping, `null` 타입을 보존합니다.
3. Process 전용 `--host`, `--port`가 해당 서비스 listener를 마지막으로 override합니다.

```bash
MYSTACK_CONFIG_FILE=config/runtime/mystack.yaml \
MYSTACK__LOGGING__LEVEL=DEBUG \
MYSTACK__PROXY__REQUEST_TIMEOUT_SECONDS=600 \
MYSTACK__MANAGEMENT__CONSOLE__REFRESH_INTERVAL_SECONDS=5 \
mystack-proxy
```

민감한 override path는 로그에서 가립니다. Production credential은 commit된 YAML에 넣지 말고
배포 시 주입합니다. Mystack management/UI 엔드포인트에는 의도적으로 인증 설정이 없으므로
신뢰하는 로컬 network 안에서만 사용해야 합니다. Docker의 일반 환경 설정과
[secret](https://docs.docker.com/compose/how-tos/use-secrets/) 구분을 따르세요.

<!-- section: docker-modes -->
## Docker 실행 방식

일반 사용자는 `compose.ghcr.yaml`을 사용합니다. 게시 image마다 같은 release에서 검토한
`/etc/mystack/mystack.yaml`이 포함됩니다.
`MYSTACK_IMAGE_TAG`는 필수입니다. Digest를 고정할 때는 component별 전체 image reference를
`MYSTACK_PROXY_IMAGE`, `MYSTACK_EMR_IMAGE`, `MYSTACK_GLUE_IMAGE`로 지정할 수 있습니다. Compose가
nested fallback을 평가하므로 세 override를 모두 써도 tag를 정의해야 합니다.

게시 환경을 바꾸려면 image와 같은 Git tag에서 `config/runtime/mystack.yaml`과
`compose.mount-config.yaml`을 받은 뒤 read-only mount를 사용합니다.

```bash
MYSTACK_CONFIG_FILE="$PWD/mystack.yaml" \
docker compose -f compose.ghcr.yaml -f compose.mount-config.yaml up --detach --wait
```

Mounted 파일을 수정한 뒤 해당 container를 재시작합니다. 설정은 process 시작 시 한 번만
읽으며 일부 값만 적용된 hot reload는 하지 않습니다.

Repository 관리자는 `make up CONFIG=config/runtime/mystack.yaml`로 `MYSTACK_CONFIG_SOURCE` build argument를
사용할 수 있습니다. 이 원본 build 경로는 [개발 환경 안내](development.ko.md)에 있으며 image
사용자에게 필요하지 않습니다.

<!-- section: sections -->
## 주요 section

[전체 설정 레퍼런스](configuration-reference.generated.md)는 실행 환경 schema와 기본값에서 생성하며,
`make configuration-reference-check`가 CI에서 drift를 실패 처리합니다.

| 경로 | 책임 |
| --- | --- |
| `logging` | 구조화 log level과 format 계약 |
| `management.console` | Browser 갱신, SSE polling/연결 deadline, log buffer 상한 |
| `management.diagnostics` | 인증 없는 thread/task stack 활성화와 최대 깊이 |
| `proxy` | listener, fallback, outbound 제한 시간, 확장 가능한 route registry |
| `localstack` | S3 엔드포인트, region, account, 로컬 credential, path-style 동작 |
| `emr` | 작업 저장소, deadline, process 정책, release 프로필, API 작업 limit |
| `glue` | 영속 SQLite 카탈로그, 카탈로그 ID, paging, partition expression/fault 정책, optimizer, 실행 환경 프로필 |
| `runtime_profiles` | Spark command/master/package/conf/parser option과 Glue version |
| `tests` | Unit/계약/E2E/Compose deadline과 black-box 클라이언트/실행 환경 설정 |

새 설정은 YAML에 추가하고 해당 composition-root 설정 어댑터에서 typed value로
mapping하며 설정 테스트와 한·영 문서를 함께 추가합니다. 안쪽 Domain/Application module은
파일이나 environment를 읽지 않고 typed policy/value object만 받습니다.

`glue.partition_expressions`는 제한이 있는 `GetPartitions.Expression` compiler를 설정합니다.
`max_length` 기본값은 공식 API의 2,048자 제한이고, `max_tokens`는 parser 작업량을 제한하며,
`supported_key_types`는 type 호환 프로필을 정의합니다. 자세한 내용은 [partition expression
protocol](protocols/glue/glue-partition-expressions.ko.md)을 참고하세요.

`glue.sqlite`는 유일한 영속 Glue 카탈로그 store를 설정합니다. `database_file`은 absolute가 아니면
`glue.data_root` 아래에서 해석합니다. Database 파일 하나만 mount하지 말고 parent directory 전체를
write 가능하게 mount해야 합니다. WAL은 그곳에 `-wal`, `-shm` sibling을 유지합니다. Image의 고정한
private DB-API는 schema나 카탈로그 파일을 만들기 전에 검증합니다. WAL이 기본이며 검증에 실패하면
시작을 거부합니다. `rollback`은 명시적인 개발용 escape hatch이고 자동 fallback이 아닙니다.

| Key | 효과 |
| --- | --- |
| `database_file` | 정규화한 영속 카탈로그 path; 상대 path는 `glue.data_root` 아래에서 해석 |
| `driver.module` | image 또는 명시적인 개발 driver가 선택하는 private DB-API module |
| `driver.expected_version` | WAL에 필요한 원본-built SQLite의 정확한 version |
| `driver.minimum_wal_version` | 안전한 WAL의 최저 version; `3.51.3` 이상이어야 함 |
| `driver.manifest_file` | WAL 시작 검증 절차에서 원본-build provenance를 확인하는 manifest |
| `journal_mode` | 기본 `wal` 또는 명시적 `rollback` (`DELETE` journal) |
| `synchronous` | SQLite durability 설정: `off`, `normal`, `full`, `extra` |
| `busy_timeout_milliseconds` | busy SQLite API 작업 하나를 기다리는 최대 시간 |
| `retry_limit` | busy writer 결과 뒤에 추가하는 상한 있는 retry 횟수 |
| `checkpoint.mode` | 요청하는 maintenance checkpoint mode: `passive`, `full`, `restart`, `truncate` |
| `checkpoint.auto_checkpoint_pages` | SQLite 자동 WAL checkpoint page threshold |

JSON 카탈로그 fallback이나 migration은 없습니다. Durability, 같은 host WAL 제한, backup 절차, logging,
수정 경계는 [Glue SQLite runtime 계약](protocols/glue/glue-sqlite-runtime.ko.md)에, Iceberg pointer commit은
[SQLite transaction 계약](protocols/glue/glue-iceberg-commits.ko.md)에 있습니다.

Glue Open Table Format 메타데이터는 주입한 S3 port를 통해 공통 `localstack.endpoint_url`, region,
credential, path-style 설정을 사용합니다. Application은 Compose 서비스 name을 가정하지 않으며
설정한 S3 bucket은 미리 존재해야 합니다. Create/update 순서, candidate cleanup, 제외 범위는
[Open Table Format 입력 protocol](protocols/glue/glue-open-table-format.ko.md)에 있습니다. Endpoint와
credential은 AWS 공식 [SDK 엔드포인트
설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)을 따릅니다.

`glue.table_optimizers`는 managed Iceberg optimizer scheduler와 제한 시간이 있는 Glue 5 Spark
subprocess를 설정합니다. Relative `work_root`는 `glue.data_root` 아래에서 해석합니다.
`catalog_endpoint_url`은 Glue container 자기 자신에서 보이는 엔드포인트이고 `catalog_name`은
Iceberg Spark 카탈로그 이름입니다. 모든 주기, 동시 실행 수, history 상한, 연속 실패 비활성화
기준, 실행 파일, submit argument, process 제한 시간과 terminate grace period를 파일로 받습니다.

```yaml
glue:
  table_optimizers:
    enabled: true
    work_root: table-optimizer-runs
    catalog_endpoint_url: http://127.0.0.1:8080
    catalog_name: mystack
    scheduler:
      poll_interval_seconds: 2
      initial_delay_seconds: 2
      max_concurrent_runs: 1
      compaction_interval_seconds: 86400
      history_limit: 100
      compaction_failure_limit: 4
    worker:
      spark_submit: /opt/mystack/bin/spark-submit
      submit_args: [--master, "local[*]"]
      timeout_seconds: 1800
      terminate_grace_seconds: 10
```

S3 엔드포인트, region, 로컬 credential은 `localstack` 설정을 사용하고 카탈로그 location은 계속
`s3://` URI로 적습니다. API, lifecycle, log와 수정 경계는 [managed optimizer
protocol](protocols/glue/glue-table-optimizers.ko.md)을 참고하세요. 세 managed type의 공식 근거는
AWS [table optimizer 안내](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html)입니다.

`glue.fault_injection`은 기본적으로 꺼져 있습니다. 활성화하면 rule 하나가 구현된 API 작업
하나와 `OperationTimeoutException` 또는 `InternalServiceException` 중 하나를 선택합니다. 한
API 작업에는 rule 하나만 둘 수 있습니다. 공통 모델의 요청 구조와 value 검증을 먼저 수행한 뒤 설정된 실패가
Catalog 조회나 mutation 전에 handler를 중단합니다. Rule은 시작 시 mounted 파일에서 한 번
읽습니다.

```yaml
glue:
  fault_injection:
    enabled: true
    rules:
      - id: timeout-get-table
        operation: GetTable
        error_code: OperationTimeoutException
        message: 결정적 test를 위해 주입한 timeout
```

인증·인가 오류는 설정할 수 없습니다. 실패 시나리오가 끝나면 rule을 제거하거나 비활성화하고
Glue container를 재시작하세요. 우선순위와 log는 [Glue 오류 결정
protocol](protocols/glue/glue-error-decisions.ko.md)을 참고하세요.

`management.console.refresh_interval_seconds`는 선택한 EMR 또는 Glue workspace의 선택 상태를
유지하는 polling 주기이며 최소 0.5초입니다. 각 emulator가 서비스 소유 UI 설정 엔드포인트에서
값을 제공하므로 browser code에는 환경별 interval이 없습니다. 현재 release는 표준 browser timer
계약인 [`Window.setInterval`](https://developer.mozilla.org/en-US/docs/Web/API/Window/setInterval)을
사용합니다.
`log_stream_poll_interval_seconds`는 SSE 연결 안에서 최대 크기가 정해진 EMR chunk를 조회하는 주기,
`log_stream_timeout_seconds`는 주기적 재연결을 강제하는 deadline,
`log_buffer_bytes`는 browser stdout/stderr별 memory 상한입니다. Protocol은 HTML
[Server-Sent Events 명세](https://html.spec.whatwg.org/multipage/server-sent-events.html)를 따릅니다.

`emr.shutdown_timeout_seconds`는 새 scheduling을 멈춘 뒤 서비스 종료 전체를 제한합니다. 이
deadline 안에서 EMR은 소유한 driver task를 cancel/await하고,
`emr.terminate_grace_seconds`로 bootstrap/Spark child를 terminate 또는 kill한 뒤 lifecycle이
소유한 log publisher와 산출물 클라이언트를 닫습니다. Bootstrap별·Step별 실행 제한 시간과는 별도
값입니다. 기반 동작은 Python 공식
[`asyncio.wait_for`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for) 문서를
따릅니다.

EMR image는 bootstrap과 Spark process를 항상 `hadoop`으로 실행하며 영속 Ivy mount는
`/home/hadoop/.ivy2`입니다. Bootstrap에서 만든 virtualenv는 이 사용자가 읽을 수 있는 경로에
있어야 하고 뒤 Step이 `spark.pyspark.python`, `spark.pyspark.driver.python`으로 선택해야 합니다.
Runtime 프로필이 허용 submit alias와 option을 제어하고 산출물 어댑터가 주 application과
`--py-files`, `--files`, `--jars`, `--archives` remote resource를 materialize합니다. Amazon EMR은
[Hadoop bootstrap identity](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)를,
Spark는 [제출 option](https://spark.apache.org/docs/3.5.4/submitting-applications.html)을 문서화합니다.

S3 log 게시에는 별도로 hard-code한 bucket이나 prefix가 없습니다. 각 cluster가 표준
`RunJobFlow.LogUri`를 제공하며 publisher는 `localstack.endpoint_url`, region, credential,
path-style 설정을 재사용합니다. 따라서 image 배포도 설정 가능하며 같은 boto3 S3 route로
LocalStack에 접근합니다. 정확한 내용은 [log protocol](protocols/emr/emr-log-layout.ko.md)을 참고하세요.
`emr.live_log_chunk_bytes`는 filesystem read 한 번의 크기를 제한합니다.
`emr.log_publication`은 retry 횟수, exponential backoff 범위, attempt 제한 시간을 설정합니다.
결정적인 S3 key를 사용하므로 재시도는 idempotent합니다. `emr.log_retention_seconds`는 terminal이며
publication이 완료 또는 skip된 work directory에만 적용합니다. 게시 실패 record는 의도적으로
보존합니다.

`emr.startup_clusters_file`은 `null` 또는 별도의 schema-versioned document path입니다. Relative
path는 선택한 main 설정 옆을 기준으로 해석합니다. File은 공식
[`RunJobFlow` member](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)를
사용하며 side effect 전에 전체를 검증합니다. 선택적인 `compose.emr-startup-clusters.yaml`
overlay는 명시적인 read-only [bind mount](https://docs.docker.com/engine/storage/bind-mounts/)를
구성합니다. Allowlist와 재시작 동작은 [시작 클러스터
protocol](protocols/emr/emr-startup-clusters.ko.md)을 참고하세요.

신뢰된 EMR image 초기화는 이 YAML 해석 경계보다 의도적으로 먼저 실행합니다.
`MYSTACK_EMR_PRESTART_ENABLED`, `MYSTACK_EMR_PRESTART_DIR`과 Compose host 전용
`MYSTACK_EMR_PRESTART_SOURCE`가 명시적 read-only script mount를 제어합니다. 이 값은 Domain이나
Application module에 노출하지 않습니다. File 검증, root에서 `hadoop`으로의 전환, 실행 환경 path와
환경 전달은 [EMR pre-start 계약](protocols/emr/emr-prestart.ko.md)을 참고하세요.

E2E harness는 `tests.emr_service`에서 EMR route를 찾고
`tests.emr_jar_fixture_container_path`에서 미리 빌드한 Java 시험 JAR를 복사합니다. 두 값 모두
설정이므로 Compose 서비스 이름이나 custom 실행 환경 image가 바뀌어도 테스트 code를 수정할
필요가 없습니다. JAR와 main class 제출 방식은 Spark 공식
[application submission guide](https://spark.apache.org/docs/3.5.4/submitting-applications.html)를 따릅니다.
Browser interaction deadline과 Chromium 누락을 실패로 볼지는
`tests.e2e.browser_action_timeout_seconds` 및
`tests.e2e.browser_required_environment_variable`이 가리키는 환경변수로 설정합니다.
격리된 wheel 동시 설치 제한 시간은 `tests.package_smoke_timeout_seconds`로 설정합니다.
`tests.compatibility_collection_timeout_seconds`는 type이 있는 compatibility annotation을 찾는 pytest
`--collect-only` subprocess만 제한합니다. Test body는 실행하지 않습니다.
`CompatibilityProfile.expected_duration_minutes`는 별도로 생성한 GitHub Actions 바깥 job 시간 상한이고,
선택한 계약 또는 E2E 테스트는 기존 YAML 테스트 제한 시간을 사용합니다.
`tests.e2e.glue_iceberg_contention_script`는 CI 전용 두 container optimistic-commit 시나리오에서
사용하는 image 내부 Spark job path입니다. Custom Glue image가 harness 위치를 바꾸더라도 테스트
코드를 고치지 않도록 파일 설정으로 둡니다.

Environment override를 적용한 뒤 모든 process가 전체 document를 package에 포함된
[`mystack.schema.json`](../shared/src/mystack/aws_protocol/mystack.schema.json)으로 검증합니다.
Unknown key, 누락 member, 잘못된 URL/account ID/port, 0 이하 deadline은 시작 전에 정확한
dotted path와 함께 실패합니다. Schema는 공식
[JSON Schema 2020-12 specification](https://json-schema.org/draft/2020-12/json-schema-core)을
사용합니다.

<!-- section: reproducibility -->
## 재현 가능한 build 입력

- `uv.lock`: 개발 dependency lock
- `requirements/{proxy,emr,glue}.txt`: `make requirements`가 생성하는 hash lock
- CI의 `scripts/development/export_requirements.py --check`: lockfile/export drift 차단
- 기본 container base: immutable multi-architecture digest; 의도적 변경은 Compose 변수 사용
- Spark archive: version argument와 공개 SHA-512 검증
- Runtime 프로필과 실제 Spark/Hive/Iceberg E2E: image/config 버전 불일치 탐지

Export 방식은 공식 [uv export interface](https://docs.astral.sh/uv/reference/cli/#uv-export)를
따릅니다.
