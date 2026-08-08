<!-- doc-id: console -->
<!-- lang: ko -->

[한국어](console.ko.md) | [English](console.md)

# 관리 Console과 Resource API

Service-aware AWS Console 스타일 UI는 public Proxy의 `/_mystack/console`에서 제공합니다.
Dependency가 없는 HTML, CSS, native JavaScript module package이며 EMR/Glue Domain code를
import하지 않습니다. UI는 AWS protocol controller와 같은 outward adapter 원칙으로 versioned
JSON management 경계만 사용합니다. 시각 체계는
[AWS Management Console](https://aws.amazon.com/console/)을 참고합니다.

<!-- section: resource-boundary -->
## Resource 경계

| Public Proxy API | Backend API | 목적 |
| --- | --- | --- |
| `GET /_mystack/components/{component}/resources` | `GET /_mystack/management/resources` | Emulator/호환 상태와 resource tree |
| `GET /_mystack/components/emr/logs?cluster_id=...&step_id=...` | `GET /_mystack/management/logs` | 설정 크기만큼의 Step stdout/stderr tail |
| `GET /_mystack/components/emr/log-stream?...` | 반복 `GET /_mystack/management/logs/chunk` | 재연결 가능한 stdout/stderr SSE stream |
| `GET /_mystack/components/{component}/diagnostics/threads` | `GET /_mystack/diagnostics/threads` | 실행 중 Python thread stack |
| `GET /_mystack/components/{component}/diagnostics/tasks` | `GET /_mystack/diagnostics/tasks` | 실행 중 asyncio task stack |

EMR 변경 작업은 Console 전용 command controller 대신 boto3와 같은 public AWS JSON 1.1
endpoint를 의도적으로 사용합니다.

| Console 작업 | AWS operation |
| --- | --- |
| Cluster 생성 | `RunJobFlow` |
| Spark Step 제출 | `AddJobFlowSteps` |
| 실행 중인 Step 취소 | `CancelSteps` |
| Cluster 종료 보호 설정/해제 | `SetTerminationProtection` |
| Cluster 종료 | `TerminateJobFlows` |

Browser는 문서화된 `X-Amz-Target`과 request 구조를 전송합니다. 따라서 Proxy routing, pinned
model validation, application handler, state transition, response validation, modeled AWS error가
boto3 경로와 동일합니다. Console alert는 AWS error code와 request ID를 보존합니다.
[EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)를 기준으로
합니다.

<!-- section: service-workflows -->
## Service별 workflow

EMR workspace는 cluster 이름, ID, 상태를 목록으로 제공하고 detail view에서 release, instance
수, `LogUri`, 종료 보호, bootstrap action, tag, lifecycle timestamp를 보여 줍니다. Steps table은
상태, 실행 시간, failure detail, 취소 가능 여부를 추적합니다. Step을 선택하면 stdout/stderr와
S3 publication record를 확인할 수 있습니다. 생성 form은 한 줄에 argument 하나, 한 줄에
`key=value` property/tag 하나를 받으며 모든 값은 array로 전달되고 shell parsing하지 않습니다.
Release 선택지는 browser 상수가 아니라 EMR service에 설정된 release profile에서 가져옵니다.
Service role, Step concurrency, visibility, instance 동작은 문서화된 `RunJobFlow` member로
mapping합니다.

Glue workspace는 database → table → detail explorer입니다. Table detail은 일반 column,
partition key, partition, table parameter, storage location, version metadata, lossless raw view를
구분해 제공합니다. Glue type string은 emulator가 별도 제한을 만들지 않고 그대로 표시하며
[Glue type system 동작](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)을 기준으로
합니다. Glue Job, JobRun, Crawler는 범위에 포함하지 않습니다.

Console은 선택한 service를 갱신할 때 선택된 cluster, Step, database, table을 유지합니다.
Resource polling은 최소 0.5초인 `management.console.refresh_interval_seconds`를 사용합니다.
Step output은 최대 크기가 정해진 byte offset read 위에서 HTML
[Server-Sent Events protocol](https://html.spec.whatwg.org/multipage/server-sent-events.html)을
사용합니다. **Pause follow**는 offset을 보존한 채 network read를 멈추고 **Resume follow**는 그
offset부터 재연결합니다. **Download**는 browser에 현재 남은 stdout/stderr를 내보냅니다. Proxy는
한 SSE 연결을 `log_stream_timeout_seconds`로 제한하고 browser가 자동 재연결합니다.
`log_buffer_bytes`는 browser tab의 무제한 memory 증가를 막습니다.

EMR은 cluster/Step lifecycle 상세, tag, release, application, bootstrap 요약, failure detail,
log tail을 제공합니다. Glue는 설정 catalog의 database/table/partition tree와 Hive/Iceberg에
필요한 type/storage field, parameter, table version을 제공합니다. API가 emulator mode와
구현/upstream operation 수를 명시하므로 UI가 AWS 완전 호환으로 오해하게 만들지 않습니다.

EMR Step을 선택하면 local stdout/stderr와 versioned S3 LogUri publication record를 함께
표시합니다. Record는 pending, skipped, published, failed, unreadable 상태를 구분하고 성공 시
Step 및 synthetic local-driver object key 전체를 보여 줍니다. `containers/`를 YARN output으로
해석하기 전에 [EMR log 배치](protocols/emr-log-layout.ko.md)를 확인하세요.
Step 실행 중 EMR이 재시작되면 Console은 durable execution journal에서 terminal **recovered
logs** projection을 추가하고 끝나지 않은 S3 게시를 다시 시도합니다. 이 projection은
process-local boto3 cluster를 재생성하지 않습니다. 따라서 이전 ID의 `DescribeCluster`는 계속
modeled not-found error를 반환합니다. Retention은 terminal이면서 publication 상태가
`published` 또는 `skipped`인 record만 지우며 upload 실패 record는 복구를 위해 남깁니다.

각 service management adapter는 자기 Application/Domain read model을 import해 JSON으로
변환할 수 있습니다. Proxy와 UI는 이 JSON 계약만 압니다. 따라서 새 emulator는 backend
resource endpoint와 일반 Proxy route만 제공하면 되고 UI가 그 service Python package를
알 필요가 없습니다.

<!-- section: security -->
## 보안과 로깅

Resource/log endpoint는 `management.diagnostics.enabled`와 선택적 bearer token을 함께
사용합니다. Proxy는 선택한 backend로 `Authorization` header와 query parameter만 전달합니다.
모든 인증 결정, resource snapshot, log read, Proxy 전달 경계는 구조화 before/after/failure
event를 기록합니다. Step argument는 값 대신 개수만 노출하지만 stdout/stderr에는 workload
데이터가 있을 수 있으므로 공유 환경에서 보호해야 합니다. AWS의
[EMR log file 지침](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)을
기준으로 합니다.

Bearer token은 Mystack management read를 보호하지만 emulated AWS endpoint를 보호하지는
않습니다. Console mutation은 해당 endpoint에 보내는 boto3 호출과 정확히 같은 인증 범위를
갖고 Mystack local mode는 production IAM enforcement를 제공한다고 주장하지 않습니다. 신뢰할
수 없는 network에 Proxy를 노출하지 마세요.

<!-- section: browser-e2e -->
## 접근성과 Browser E2E

Skip link, 명시적 form label, polite live status, 이름 있는 control, responsive layout, 보이는
keyboard focus, Left/Right/Home/End를 지원하는 WAI-ARIA tab을 제공합니다. 구현은
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)을 따릅니다. Playwright
E2E는 browser에서 cluster를 생성·종료하고, Step 제출·추적·취소 전 live output 확인,
pause/resume/download와 log publication을 검증하며,
복합 Glue schema와 partition을 탐색합니다. 또한 label, role, keyboard 이동, 진단, browser
console error를 검증합니다. CI는 Chromium을 설치해 필수 실행하며 local은 Chromium이 없을
때만 skip합니다.
`uv run playwright install chromium`으로 설치할 수 있습니다.

Browser action timeout과 CI 필수 여부를 나타내는 환경변수 이름은 각각
`tests.e2e.browser_action_timeout_seconds`,
`tests.e2e.browser_required_environment_variable`에서 설정합니다.
