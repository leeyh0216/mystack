<!-- doc-id: observability -->
<!-- lang: en -->

[한국어](observability.ko.md) | [English](observability.md)

# Observability and diagnostics

Mystack emits structured JSON at controllers, component boundaries, state transitions, and every external side effect. This follows the [AWS Well-Architected observability guidance](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/observability.html).

<!-- section: event-phases -->
## Required event phases

- `*.received` or `*.started` before work
- `*.completed` after successful work with duration and result metadata
- `*.failed` on technical failure with exception and actionable `fix_hint`
- `*.service_error` for modeled AWS behavior without a Python traceback
- `protocol.operation_registry.*` while composing reviewed operation families at startup
- `*.transitioned` for domain state changes with before/after/reason

Repository, S3, process, container, and outbound HTTP adapters must emit all applicable phases.

EMR LogUri publication emits `emr.step_logs.publish.*` around the complete archive and
`emr.step_log_object.put.*` around every S3 object. Failures contain the cluster/Step, safe bucket
and key evidence, partial object count, and a `fix_hint`, while the local publication record remains
available through the management endpoint. See the [log layout contract](protocols/emr-log-layout.md).

Preconfigured clusters emit `emr.startup_clusters.load.*` before/after whole-file validation,
`emr.startup_clusters.provision.*` around the plan, and `emr.startup_cluster.create.*` for each
application-port call. Source, fingerprint, safe counts, definition index, cluster ID, and repair
location make a future botocore mapping drift diagnosable. See the [startup cluster
contract](protocols/emr-startup-clusters.md).

Trusted image initialization emits `emr.prestart.scan.*`, per-file
`emr.prestart.script.before`/`after`/`failed`, and
`emr.entrypoint.privilege_drop.before`/`failed`. It logs only a script basename, safe ownership and
mode, SHA-256 prefix, duration or exit code, and a `fix_hint`; values and script contents remain
private. See the [EMR pre-start contract](protocols/emr-prestart.md).

<!-- section: fields -->
## Common fields

`service`, `component`, `request_id`, `operation`, `api_version`, `model_fingerprint`, `resource_id`, `state_before`, `state_after`, `duration_ms`, and `fix_hint` where relevant.

Never log Authorization, access/secret keys, management tokens, complete request payloads, or frame locals. Payload diagnostics use byte length and SHA-256 prefix. Configuration logs use source, fingerprint, and redacted override paths.

<!-- section: diagnostics -->
## Live diagnostics

- `GET /_mystack/diagnostics/threads`: Python threads and source stack lines
- `GET /_mystack/diagnostics/tasks`: asyncio tasks and source stack lines

Both honor YAML `management.diagnostics.enabled`, `stack_limit`, and optional `token`. A configured token requires `Authorization: Bearer ...`. Access attempts are audited. Python documents the non-deadlocking snapshot behavior of [`sys._current_frames`](https://docs.python.org/3/library/sys.html#sys._current_frames).

Use `make threads` or `make tasks`. Stack source is operationally sensitive even without locals, so shared deployments must configure a management token and restrict network access.

<!-- section: drift -->
## Upstream drift diagnosis

Model load and validation events contain botocore version, service API version, model fingerprint, operation, and input shape. A fingerprint change points first to the protocol facade; an operation shape change points to that service inbound mapper and contract tests.

`proxy.routing.fallback` records safe protocol evidence (target prefix, SigV4 signing name, host
prefix, content type, and parsed SDK versions) without credentials or the full User-Agent. Its
`fix_hint` distinguishes a configuration-only route metadata update from an actual evidence-parser
change in `routing.py`.

`proxy.forward.completed` records raw response byte length, upstream content encoding, and whether
the injected client had already decoded the body (`response_body_decoded`, normally `false`). If an
SDK reports an S3 flexible-checksum mismatch, inspect this event and `mystack.proxy.forwarder`
before changing a service emulator or object payload.
