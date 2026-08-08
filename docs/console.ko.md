# 관리 Console과 Resource API

한국어 | [English](console.md)

AWS Console 스타일 UI는 public Proxy의 `/_mystack/console`에서 제공합니다. Dependency가
없는 package 내 HTML asset이며 EMR/Glue Domain code를 import하지 않습니다. UI는 AWS
protocol controller와 같은 outward adapter 원칙으로 versioned JSON management 경계만
사용합니다. 시각 체계는 [AWS Management Console](https://aws.amazon.com/console/)을 참고합니다.

## Resource 경계

| Public Proxy API | Backend API | 목적 |
| --- | --- | --- |
| `GET /_mystack/components/{component}/resources` | `GET /_mystack/management/resources` | Emulator/호환 상태와 resource tree |
| `GET /_mystack/components/emr/logs?cluster_id=...&step_id=...` | `GET /_mystack/management/logs` | 설정 크기만큼의 Step stdout/stderr tail |
| `GET /_mystack/components/{component}/diagnostics/threads` | `GET /_mystack/diagnostics/threads` | 실행 중 Python thread stack |
| `GET /_mystack/components/{component}/diagnostics/tasks` | `GET /_mystack/diagnostics/tasks` | 실행 중 asyncio task stack |

EMR은 cluster/Step lifecycle 상세, tag, release, application, bootstrap 요약, failure detail,
log tail을 제공합니다. Glue는 설정 catalog의 database/table/partition tree와 Hive/Iceberg에
필요한 type/storage field, parameter, table version을 제공합니다. API가 emulator mode와
구현/upstream operation 수를 명시하므로 UI가 AWS 완전 호환으로 오해하게 만들지 않습니다.

각 service management adapter는 자기 Application/Domain read model을 import해 JSON으로
변환할 수 있습니다. Proxy와 UI는 이 JSON 계약만 압니다. 따라서 새 emulator는 backend
resource endpoint와 일반 Proxy route만 제공하면 되고 UI가 그 service Python package를
알 필요가 없습니다.

## 보안과 로깅

Resource/log endpoint는 `management.diagnostics.enabled`와 선택적 bearer token을 함께
사용합니다. Proxy는 선택한 backend로 `Authorization` header와 query parameter만 전달합니다.
모든 인증 결정, resource snapshot, log read, Proxy 전달 경계는 구조화 before/after/failure
event를 기록합니다. Step argument는 값 대신 개수만 노출하지만 stdout/stderr에는 workload
데이터가 있을 수 있으므로 공유 환경에서 보호해야 합니다. AWS의
[EMR log file 지침](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)을
기준으로 합니다.

## 접근성과 Browser E2E

Skip link, 명시적 form label, polite live status, 이름 있는 control, responsive layout, 보이는
keyboard focus, Left/Right/Home/End를 지원하는 WAI-ARIA tab을 제공합니다. 구현은
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)을 따릅니다. Playwright
E2E가 label, role, keyboard 이동, resource detail, 진단, browser console error를 검증합니다.
CI는 Chromium을 설치해 필수 실행하며 local은 Chromium이 없을 때만 skip합니다.
`uv run playwright install chromium`으로 설치할 수 있습니다.

Browser action timeout과 CI 필수 여부를 나타내는 환경변수 이름은 각각
`tests.e2e.browser_action_timeout_seconds`,
`tests.e2e.browser_required_environment_variable`에서 설정합니다.
