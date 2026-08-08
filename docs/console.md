# Management console and resource API

[한국어](console.ko.md) | English

The AWS-console-inspired UI is served at `/_mystack/console` on the public Proxy endpoint. It is a
dependency-free packaged HTML asset and never imports EMR or Glue Domain code. The UI consumes a
versioned JSON management boundary, following the same outward-adapter rule as the AWS protocol
controllers. The visual vocabulary follows the [AWS Management Console](https://aws.amazon.com/console/).

## Resource boundary

| Public Proxy API | Backend API | Purpose |
| --- | --- | --- |
| `GET /_mystack/components/{component}/resources` | `GET /_mystack/management/resources` | Emulator/compatibility status and resource tree |
| `GET /_mystack/components/emr/logs?cluster_id=...&step_id=...` | `GET /_mystack/management/logs` | Configured tail of Step stdout/stderr |
| `GET /_mystack/components/{component}/diagnostics/threads` | `GET /_mystack/diagnostics/threads` | Live Python thread stacks |
| `GET /_mystack/components/{component}/diagnostics/tasks` | `GET /_mystack/diagnostics/tasks` | Live asyncio task stacks |

EMR exposes cluster and Step lifecycle detail, tags, release, applications, bootstrap summaries,
failure detail, and log tails. Glue exposes the configured catalog's database/table/partition tree,
Hive/Iceberg-relevant type and storage fields, parameters, and table versions. The API identifies
the emulator mode and the exact implemented/upstream operation counts so the UI cannot imply full
AWS compatibility.

Service management adapters may import their own Application/Domain read models and translate
them to JSON. Proxy and UI code know only this JSON contract. Adding a new emulator therefore
requires implementing the backend resource endpoint and registering a normal Proxy route; the UI
does not need the new service's Python package.

## Security and logging

Resource and log endpoints reuse `management.diagnostics.enabled` and its optional bearer token.
The Proxy forwards only the `Authorization` header and query parameters to the selected backend.
Every authorization decision, resource snapshot, log read, and Proxy forwarding boundary emits
structured before/after/failure events. Step arguments are summarized by count rather than exposed;
stdout/stderr can still contain workload data and should be protected in shared environments.
AWS documents the sensitivity and lifecycle of [EMR log files](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html).

## Accessibility and browser E2E

The console provides a skip link, explicit form labels, a polite live status region, named controls,
responsive layouts, visible keyboard focus, and WAI-ARIA tabs with Left/Right/Home/End navigation.
The implementation follows the [WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).
Playwright E2E verifies labels, roles, keyboard navigation, resource detail, diagnostics, and browser
console errors. CI installs Chromium and makes the test required; local runs skip only when Chromium
is absent. Install it with `uv run playwright install chromium`.

Browser action timeout and the CI-required environment-variable name live in
`tests.e2e.browser_action_timeout_seconds` and
`tests.e2e.browser_required_environment_variable`.
