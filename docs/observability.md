# Observability and diagnostics

[한국어](observability.ko.md) | English

Mystack emits structured JSON at controllers, component boundaries, state transitions, and every external side effect. This follows the [AWS Well-Architected observability guidance](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/observability.html).

## Required event phases

- `*.received` or `*.started` before work
- `*.completed` after successful work with duration and result metadata
- `*.failed` on technical failure with exception and actionable `fix_hint`
- `*.service_error` for modeled AWS behavior without a Python traceback
- `*.transitioned` for domain state changes with before/after/reason

Repository, S3, process, container, and outbound HTTP adapters must emit all applicable phases.

## Common fields

`service`, `component`, `request_id`, `operation`, `api_version`, `model_fingerprint`, `resource_id`, `state_before`, `state_after`, `duration_ms`, and `fix_hint` where relevant.

Never log Authorization, access/secret keys, management tokens, complete request payloads, or frame locals. Payload diagnostics use byte length and SHA-256 prefix. Configuration logs use source, fingerprint, and redacted override paths.

## Live diagnostics

- `GET /_mystack/diagnostics/threads`: Python threads and source stack lines
- `GET /_mystack/diagnostics/tasks`: asyncio tasks and source stack lines

Both honor YAML `management.diagnostics.enabled`, `stack_limit`, and optional `token`. A configured token requires `Authorization: Bearer ...`. Access attempts are audited. Python documents the non-deadlocking snapshot behavior of [`sys._current_frames`](https://docs.python.org/3/library/sys.html#sys._current_frames).

Use `make threads` or `make tasks`. Stack source is operationally sensitive even without locals, so shared deployments must configure a management token and restrict network access.

## Upstream drift diagnosis

Model load and validation events contain botocore version, service API version, model fingerprint, operation, and input shape. A fingerprint change points first to the protocol facade; an operation shape change points to that service inbound mapper and contract tests.

