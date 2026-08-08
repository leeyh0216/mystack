<!-- doc-id: console -->
<!-- lang: en -->

[한국어](console.ko.md) | [English](console.md)

# Management console and resource API

The service-aware, AWS-console-inspired UI is served at `/_mystack/console` on the public Proxy
endpoint. It is a dependency-free package of HTML, CSS, and native JavaScript modules and never
imports EMR or Glue Domain code. The UI consumes a
versioned JSON management boundary, following the same outward-adapter rule as the AWS protocol
controllers. The visual vocabulary follows the [AWS Management Console](https://aws.amazon.com/console/).

<!-- section: resource-boundary -->
## Resource boundary

| Public Proxy API | Backend API | Purpose |
| --- | --- | --- |
| `GET /_mystack/components/{component}/resources` | `GET /_mystack/management/resources` | Emulator/compatibility status and resource tree |
| `GET /_mystack/components/emr/logs?cluster_id=...&step_id=...` | `GET /_mystack/management/logs` | Configured tail of Step stdout/stderr |
| `GET /_mystack/components/{component}/diagnostics/threads` | `GET /_mystack/diagnostics/threads` | Live Python thread stacks |
| `GET /_mystack/components/{component}/diagnostics/tasks` | `GET /_mystack/diagnostics/tasks` | Live asyncio task stacks |

EMR mutations intentionally use the same public AWS JSON 1.1 endpoint as boto3 rather than a
Console-only command controller:

| Console action | AWS operation |
| --- | --- |
| Create cluster | `RunJobFlow` |
| Submit Spark Step | `AddJobFlowSteps` |
| Cancel active Step | `CancelSteps` |
| Protect/unprotect cluster | `SetTerminationProtection` |
| Terminate cluster | `TerminateJobFlows` |

The browser supplies the documented `X-Amz-Target` and request shape. Proxy routing, pinned model
validation, application handler, state transition, response validation, and modeled AWS errors are
therefore identical to the boto3 path. The Console preserves the AWS error code and request ID in
its alert. See the [EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).

<!-- section: service-workflows -->
## Service-aware workflows

The EMR workspace lists clusters by name, ID, and state; its detail view presents release,
instance count, `LogUri`, termination protection, bootstrap actions, tags, and lifecycle
timestamps. The Steps table tracks state, duration, failure detail, and cancellation availability.
Selecting a Step opens stdout/stderr and its S3 publication record. The create forms accept one
argument per line and one `key=value` property/tag per line; values are passed as arrays and are
never shell-parsed. Release choices come from the EMR service's configured release profiles rather
than a browser constant; service role, Step concurrency, visibility, and instance behavior map to
the documented `RunJobFlow` members.

The Glue workspace is a database → table → detail explorer. Table detail separates ordinary
columns, partition keys, partitions, table parameters, storage locations, version metadata, and a
raw lossless view. Glue type strings are displayed without inventing an emulator type restriction,
matching the [Glue type-system behavior](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html).
Glue Jobs, JobRuns, and Crawlers remain out of scope.

The Console refreshes the selected service without losing the selected cluster, Step, database, or
table. Its interval is `management.console.refresh_interval_seconds` and must be at least 0.5
seconds. This release uses polling; resumable streaming is tracked separately.

EMR exposes cluster and Step lifecycle detail, tags, release, applications, bootstrap summaries,
failure detail, and log tails. Glue exposes the configured catalog's database/table/partition tree,
Hive/Iceberg-relevant type and storage fields, parameters, and table versions. The API identifies
the emulator mode and the exact implemented/upstream operation counts so the UI cannot imply full
AWS compatibility.

Selecting an EMR Step shows local stdout/stderr plus its versioned S3 LogUri publication record.
The record distinguishes pending, skipped, published, failed, and unreadable states; published
records list the exact Step and synthetic local-driver object keys. See the
[EMR log layout](protocols/emr-log-layout.md) before interpreting `containers/` as YARN output.

Service management adapters may import their own Application/Domain read models and translate
them to JSON. Proxy and UI code know only this JSON contract. Adding a new emulator therefore
requires implementing the backend resource endpoint and registering a normal Proxy route; the UI
does not need the new service's Python package.

<!-- section: security -->
## Security and logging

Resource and log endpoints reuse `management.diagnostics.enabled` and its optional bearer token.
The Proxy forwards only the `Authorization` header and query parameters to the selected backend.
Every authorization decision, resource snapshot, log read, and Proxy forwarding boundary emits
structured before/after/failure events. Step arguments are summarized by count rather than exposed;
stdout/stderr can still contain workload data and should be protected in shared environments.
AWS documents the sensitivity and lifecycle of [EMR log files](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html).

The bearer token protects Mystack management reads, not the emulated AWS endpoint. Console
mutations have exactly the same authorization scope as boto3 calls to that endpoint; Mystack local
mode does not claim production IAM enforcement. Do not expose the Proxy to an untrusted network.

<!-- section: browser-e2e -->
## Accessibility and browser E2E

The console provides a skip link, explicit form labels, a polite live status region, named controls,
responsive layouts, visible keyboard focus, and WAI-ARIA tabs with Left/Right/Home/End navigation.
The implementation follows the [WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).
Playwright E2E creates and terminates a cluster through the browser, submits/tracks/cancels a Step,
checks its log publication, explores a complex Glue schema and partition, and verifies labels,
roles, keyboard navigation, diagnostics, and browser console errors. CI installs Chromium and makes
the test required; local runs skip only when Chromium is absent. Install it with
`uv run playwright install chromium`.

Browser action timeout and the CI-required environment-variable name live in
`tests.e2e.browser_action_timeout_seconds` and
`tests.e2e.browser_required_environment_variable`.
