<!-- doc-id: console -->
<!-- lang: ko -->

[한국어](console.ko.md) | [English](console.md)

# Service가 소유하는 관리 UI

Mystack은 EMR과 Glue에 분리된 React·TypeScript application을 제공합니다. 각 emulator가 자기
application을 build·package·serve하고 Proxy는 안정적인 gateway path만 제공합니다. Service
application은 root `@mystack/ui` workspace의 primitive를 조립하고 같은 Tailwind design set을
사용합니다. 구현은 공식 [React TypeScript guide](https://react.dev/learn/typescript),
[Vite production build guide](https://vite.dev/guide/build.html),
[Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite)을 따릅니다.

<!-- section: resource-boundary -->
## URL과 component 경계

| Consumer path | 소유 backend path | 목적 |
| --- | --- | --- |
| `GET /_mystack/ui/emr/` | EMR `GET /_mystack/ui/emr/` | EMR React application과 hash asset |
| `GET /_mystack/ui/glue/` | Glue `GET /_mystack/ui/glue/` | Glue React application과 hash asset |
| `GET /_mystack/ui/emr/resources` | EMR 같은 path | Cluster와 Step 조회 model |
| `GET /_mystack/ui/emr/log-stream?...` | EMR 같은 path | 재연결 가능한 stdout/stderr SSE |
| `GET /_mystack/ui/glue/resources` | Glue 같은 path | Catalog database/table/partition 조회 model |
| `GET /_mystack/ui/{service}/diagnostics/{kind}` | Service 소유 UI 진단 path | Thread 또는 asyncio task stack |

`/_mystack/console`, `/console`, `/_mystack/ui`는 호환성과 초기 접근을 위해
`/_mystack/ui/emr/`로 redirect합니다. Compose 내부에서 emulator에 직접 접근할 때도
`http://emr:8080/_mystack/ui/emr/`, `http://glue:8080/_mystack/ui/glue/`의 같은 path를 사용합니다.
Proxy는 service JSON을 해석하거나 service package를 import하지 않고 byte와 SSE frame을
전달합니다. 새 emulator는 일반 선언형 Proxy route와 service가 소유하는 `/_mystack/ui/{service}/`
계약을 제공하면 됩니다.

선택 상태는 component memory가 아니라 browser history route에 남습니다. 예를 들어
`/_mystack/ui/emr/clusters/{cluster-id}/steps/{step-id}/logs`,
`/_mystack/ui/glue/databases/{database}/tables/{table}/partitions`를 사용합니다. Refresh, link 복사,
Back, Forward를 사용해도 resource와 tab 선택을 복원합니다. 각 emulator의 history-fallback
adapter는 확장자가 없는 UI path에 entry document를 제공하지만 존재하지 않는 asset과 JSON
request는 실제 404를 유지합니다.

Root `ui/` package는 `Input`, `Select`, `Textarea`, `Checkbox`, `Button`, `Badge`, `Dialog`,
`Tabs`, panel, 정의 목록, loading/error 상태, service 중립 HTTP/polling 도구를 소유합니다.
EMR과 Glue는 이 공개 package만 import하고 서로를 import하지 않습니다. Semantic Tailwind
변수는 `ui/src/theme.css`에 있습니다. Light와 midnight set은 raw 값을 `canvas`, `surface`,
`ink`, `border`, `brand`, `positive`, `danger` 같은 이름에 mapping합니다. 이 set을 바꾸면
service component를 수정하지 않고 두 application이 함께 바뀝니다. 공식
[Tailwind theme variable 계약](https://tailwindcss.com/docs/theme)을 기준으로 합니다.

EMR 변경 작업은 boto3와 같은 public AWS JSON 1.1 endpoint를 의도적으로 사용합니다.

| UI 작업 | AWS operation |
| --- | --- |
| Cluster 생성 | `RunJobFlow` |
| Spark Step 제출 | `AddJobFlowSteps` |
| 실행 중인 Step 취소 | `CancelSteps` |
| Cluster 종료 보호 설정 또는 해제 | `SetTerminationProtection` |
| Cluster 종료 | `TerminateJobFlows` |

Browser는 문서화된 `X-Amz-Target`과 request body를 `/`로 전송합니다. 따라서 Proxy routing,
pinned model validation, application handler, 상태 전이, response validation, modeled error가
boto3와 같은 경로를 사용합니다. Operation 근거는
[EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)입니다.

<!-- section: service-workflows -->
## Service workflow

EMR application은 cluster 검색, release/`LogUri`/bootstrap/tag/timeline 상세 표시,
cluster 생성, Step 제출·취소, 종료 보호 관리, cluster 종료를 제공합니다. Release 선택지는
설정된 EMR profile에서 가져옵니다. IAM role, instance 크기, 사용자 간 visibility는 Spark local
mode에 영향을 주지 않으므로 UI에서 제거했습니다. Step은 한 줄에 argument 하나인 전체 command
vector를 받으며 browser에서 shell parsing하지 않습니다. PySpark application은 `spark-submit` 다음에
`.py` URI를 전달합니다. Interactive `pyspark` shell은 EMR Step이 아닙니다. Amazon EMR
[Spark Step 계약](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)을
따릅니다.

Step을 선택하면 제출한 `HadoopJarStep` argument vector, 실제 local process에 전달한 정확한
argument vector, service가 소유하는 live stdout/stderr, 게시 상태, pause/resume, download,
cancel control을 표시합니다. EMR은 local file을 byte offset으로 읽고 두 offset을 SSE event
ID로 게시하며 재연결 시 `Last-Event-ID`를 적용합니다.
`management.console.log_stream_timeout_seconds`는 연결 하나의 시간을 제한하고
`log_buffer_bytes`는 browser가 보관하는 stdout/stderr 크기를 제한합니다. Emulator 재시작
뒤에도 내구성 있는 복구 Step 표시와 S3 게시 상태를 확인할 수 있습니다. Synthetic
local-driver object는 [EMR log 배치](protocols/emr-log-layout.ko.md)와 AWS
[EMR log 지침](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)을
기준으로 해석합니다.

Glue application은 database → table → schema/partition/parameter/raw detail을 탐색합니다.
Glue type string을 손실 없이 유지하므로 별도 browser type system 없이 Spark Hive와 Iceberg
metadata를 확인할 수 있습니다. 동작은
[Glue Data Catalog API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html)와
[Glue type 문서](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)를 따릅니다. Glue
Job, JobRun, Crawler는 범위에 포함하지 않습니다.

두 application은 설정된 refresh interval로 service 소유 resource endpoint를 조회하고 아직
존재하는 선택 항목을 유지합니다. Controller, resource snapshot, stream open/close, backend
전달 경계, 실패를 모두 구조화 log로 기록합니다. Protocol 실패 log는 관리자가 확인할 service
UI adapter 또는 management schema를 알려 줍니다.

<!-- section: security -->
## Local 보안 model

Mystack은 UI와 진단 path에 login, management token input, bearer token validation, session,
cookie, authorization 전달을 제공하지 않습니다. Local 개발 emulator이며 IAM 또는 multi-tenant
관리 plane이 아닙니다. `management.diagnostics.enabled`로 thread/task endpoint를 없앨 수 있지만
이는 인증이 아니라 제공 여부 설정입니다.

따라서 Proxy와 emulator port를 신뢰할 수 없는 network에 노출하지 마세요. stdout/stderr,
catalog parameter, path, thread source line, task stack에는 운영상 민감한 정보가 있을 수
있습니다. 제출 application argument와 resolved command에도 secret이 들어갈 수 있으므로
credential은 더 안전한 runtime 경로로 전달하세요. 배포 환경의 container/network 경계를 사용하세요. AWS request `Authorization`은
일반 SigV4 service routing의 protocol 근거로만 남고 UI gateway는 이를 cookie와 함께 제거한
뒤 전달합니다.

<!-- section: browser-e2e -->
## 개발환경, 접근성, Browser E2E

Checkout 뒤 `npm ci`를 한 번 실행합니다. `npm run frontend:check:emr`,
`npm run frontend:check:glue`, `npm run frontend:check`를 사용할 수 있습니다. Production build는
각 Python package의 Docker multi-stage build에서 생성하며 최종 image에는 Node runtime이
없습니다. Dev Container는 고정 Node toolchain을 설치하고 pre-commit은 Python Ruff와 React
TypeScript ESLint를 모두 실행합니다. CI는 Docker E2E 전에 lint, TypeScript project reference,
Vitest, Vite build 두 개를 독립적으로 실행합니다.

공통 control은 label, description, 보이는 focus, 이름 있는 status/error 영역, responsive
layout, skip link, keyboard tab을 제공합니다. Tab은
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)에 따라
Left/Right/Home/End를 지원합니다. Playwright는 EMR cluster 생성·종료, Step 제출·추적·취소,
log 확인·pause/resume/download, S3 게시 상태를 검증합니다. 별도 Glue application으로 이동해
복합 type과 partition을 탐색하고 service 진단, keyboard 동작, browser console error도
검사합니다.

Browser 작업과 전체 E2E 시간 제한은 `tests.e2e.browser_action_timeout_seconds`,
`tests.e2e_timeout_seconds` 설정을 사용합니다. Local browser 계약을 실행할 때만
`uv run playwright install chromium`으로 설치합니다.
