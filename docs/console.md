<!-- doc-id: console -->
<!-- lang: en -->

[한국어](console.ko.md) | [English](console.md)

# Service-owned management UIs

<!-- toc:start -->
## Contents

- [URLs and component boundary](#urls-and-component-boundary)
- [Service workflows](#service-workflows)
- [Local security model](#local-security-model)
- [Development, accessibility, and browser E2E](#development-accessibility-and-browser-e2e)
<!-- toc:end -->

Mystack provides separate React and TypeScript applications for EMR and Glue. Each emulator builds,
packages, and serves its own application; the Proxy only exposes stable gateway paths. All service
applications compose primitives from the root `@mystack/ui` workspace and consume the same Tailwind
design set. The implementation follows the official [React TypeScript guide](https://react.dev/learn/typescript),
[Vite production build guide](https://vite.dev/guide/build.html), and
[Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite).

<!-- section: resource-boundary -->
## URLs and component boundary

| Consumer path | Owning backend path | Purpose |
| --- | --- | --- |
| `GET /_mystack/ui/emr/` | EMR `GET /_mystack/ui/emr/` | EMR React application and hashed assets |
| `GET /_mystack/ui/glue/` | Glue `GET /_mystack/ui/glue/` | Glue React application and hashed assets |
| `GET /_mystack/ui/emr/resources` | EMR same path | Cluster and Step read model |
| `GET /_mystack/ui/emr/log-stream?...` | EMR same path | Reconnectable stdout/stderr SSE |
| `GET /_mystack/ui/glue/resources` | Glue same path | Catalog database/table/partition read model |
| `GET /_mystack/ui/{service}/diagnostics/{kind}` | Service-owned UI diagnostics path | Thread or asyncio task stacks |

`/_mystack/console`, `/console`, and `/_mystack/ui` redirect to `/_mystack/ui/emr/` for compatibility
and onboarding. Direct emulator access uses the same paths at `http://emr:8080/_mystack/ui/emr/`
or `http://glue:8080/_mystack/ui/glue/` inside Compose. The Proxy streams bytes and SSE frames without
interpreting service JSON or importing a service package. A new emulator therefore needs a normal
declarative Proxy route and a service-owned `/_mystack/ui/{service}/` contract.

Selections are durable browser history routes rather than component-only state. Examples include
`/_mystack/ui/emr/clusters/{cluster-id}/steps/{step-id}/logs` and
`/_mystack/ui/glue/databases/{database}/tables/{table}/partitions`. Refresh, copied links, Back, and
Forward restore the selected resource and tab. Each emulator's history-fallback adapter serves the
entry document for extensionless UI paths while missing assets and JSON requests remain real 404s.

The root `ui/` package owns `Input`, `Select`, `Textarea`, `Checkbox`, `Button`, `Badge`, `Dialog`,
`Tabs`, panels, definitions, loading/error states, and service-neutral HTTP/polling utilities. EMR
and Glue import only that public package; they never import one another. Semantic Tailwind variables
live in `ui/src/theme.css`. Both the light and midnight sets map raw values to names such as
`canvas`, `surface`, `ink`, `border`, `brand`, `positive`, and `danger`. Changing that set updates
both applications without editing service components. See the official
[Tailwind theme-variable contract](https://tailwindcss.com/docs/theme).

EMR mutations intentionally use the same public AWS JSON 1.1 endpoint as boto3:

| UI action | AWS operation |
| --- | --- |
| Create cluster | `RunJobFlow` |
| Submit Spark Step | `AddJobFlowSteps` |
| Cancel active Step | `CancelSteps` |
| Protect or unprotect cluster | `SetTerminationProtection` |
| Terminate cluster | `TerminateJobFlows` |

The browser sends the documented `X-Amz-Target` and request body to `/`. Proxy routing, pinned model
validation, application handlers, state transitions, response validation, and modeled errors are
therefore shared with boto3. The [EMR API reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
remains the operation source.

<!-- section: service-workflows -->
## Service workflows

The EMR application filters clusters, renders release/`LogUri`/bootstrap/tag/timeline
details, creates a cluster, submits or cancels a Step, manages termination protection, and
terminates a cluster. It omits IAM roles, instance sizing, and cross-user visibility because they do
not affect Spark local mode. Release choices and accepted submit aliases come from configured EMR
profiles. A Step accepts the complete command argument vector with one argument per line and never
shell-parses it. A PySpark application uses `spark-submit` followed by its `.py` URI; an interactive
`pyspark` shell is not an EMR Step. This follows Amazon EMR's
[Spark Step contract](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html).

Selecting a Step opens its submitted `HadoopJarStep` argument vector, the exact resolved local
process argument vector, service-owned live stdout/stderr, publication status, pause/resume, download,
and cancel controls. EMR reads local files by byte offset, publishes SSE event IDs with both offsets,
and honors `Last-Event-ID` on reconnect. `management.console.log_stream_timeout_seconds` limits one
connection, while `log_buffer_bytes` caps stdout and stderr retained by the browser. Durable recovered
Step projections and S3 publication statuses remain visible after an emulator restart. Interpret
synthetic local-driver objects with the [EMR log layout](protocols/emr-log-layout.md) and AWS
[EMR log guidance](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html).

The Glue application explores database → table → schema/partitions/parameters/raw detail. It keeps
Glue type strings lossless so Spark Hive and Iceberg metadata are visible without a second browser
type system. The behavior follows the [Glue Data Catalog API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html)
and [Glue type documentation](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html). Glue Jobs,
JobRuns, and Crawlers remain out of scope.

Both applications poll their service-owned resource endpoint with the configured refresh interval
and preserve a still-existing selection. Every controller, resource snapshot, stream open/close,
backend forwarding boundary, and failure emits structured logs. Protocol failures identify the
service UI adapter or management schema that maintainers should inspect.

<!-- section: security -->
## Local security model

Mystack deliberately provides no login, management-token input, bearer-token validation, session,
cookie, or authorization forwarding for UI and diagnostic paths. This is a local development
emulator, not an IAM or multi-tenant administration plane. `management.diagnostics.enabled` can
remove thread/task endpoints, but it is an availability switch rather than authentication.

Consequently, do not expose the Proxy or emulator ports to an untrusted network. stdout/stderr,
catalog parameters, paths, thread source lines, and task stacks can contain operationally sensitive
data. Submitted application arguments and resolved commands are visible here and can also contain
secrets; pass credentials through a safer runtime mechanism. Use container/network boundaries supplied by the deployment environment. AWS request
`Authorization` remains relevant only as protocol evidence for normal SigV4 service routing; the UI
gateway strips it and cookies before forwarding.

<!-- section: browser-e2e -->
## Development, accessibility, and browser E2E

Run `npm ci` once after checkout. Use `npm run frontend:check:emr`,
`npm run frontend:check:glue`, or `npm run frontend:check`. Production builds are generated into
each Python package during its Docker multi-stage build; the final image has no Node runtime. The
Dev Container installs the pinned Node toolchain, and pre-commit runs both Python Ruff and React
TypeScript ESLint. CI independently runs lint, TypeScript project references, Vitest, and both Vite
builds before Docker E2E.

Shared controls provide labels, descriptions, visible focus, named status/error regions, responsive
layouts, skip links, and keyboard tabs. Tabs support Left/Right/Home/End according to the
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/). Playwright creates and
terminates an EMR cluster, submits/tracks/cancels a Step, observes/pause/resumes/downloads logs,
checks S3 publication, navigates to the separate Glue application, explores complex types and a
partition, opens service diagnostics, checks keyboard behavior, and fails on browser console errors.

Browser action and total E2E limits remain file-driven through
`tests.e2e.browser_action_timeout_seconds` and `tests.e2e_timeout_seconds`. Install a local browser
only when running the browser contract with `uv run playwright install chromium`.
