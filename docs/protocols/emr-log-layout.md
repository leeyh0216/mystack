<!-- doc-id: emr-log-layout -->
<!-- lang: en -->

[한국어](emr-log-layout.ko.md) | [English](emr-log-layout.md)

# EMR LogUri S3 layout

Mystack archives terminal Step process logs when `RunJobFlow.LogUri` is an S3 URI. The Step path
follows Amazon EMR's documented S3 layout. Spark runs in local/client mode, so application IDs below
`containers/` are deliberately synthetic and do not represent YARN applications.

<!-- section: enable -->
## Enable log archiving

Supply a bucket and optional prefix when creating the cluster. The bucket must already exist in the
configured LocalStack S3 service.

```python
cluster = emr.run_job_flow(
    Name="local-spark",
    LogUri="s3://my-logs/team-a/",
    Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
)
```

An omitted `LogUri` performs no S3 log mutation. An invalid URI or unavailable bucket does not
rewrite the Spark result; inspect the Console log tab or
`GET /_mystack/components/emr/logs?cluster_id=...&step_id=...` for the publication record.

<!-- section: layout -->
## Object layout

For `LogUri=s3://my-logs/team-a/`, cluster `j-ABC`, and Step `s-123`, Mystack writes:

```text
s3://my-logs/team-a/j-ABC/steps/s-123/controller.gz
s3://my-logs/team-a/j-ABC/steps/s-123/syslog.gz
s3://my-logs/team-a/j-ABC/steps/s-123/stdout.gz
s3://my-logs/team-a/j-ABC/steps/s-123/stderr.gz
s3://my-logs/team-a/j-ABC/containers/application_local_j_ABC_s_123/
  container_local_j_ABC_s_123_01_000001/stdout.gz
  container_local_j_ABC_s_123_01_000001/stderr.gz
```

All six objects use `Content-Encoding: gzip`. `stdout` and `stderr` contain the exact local
`spark-submit` process streams. `controller` records the local process start/exit projection.
`syslog` explicitly says that no EC2 node, YARN, or node syslog exists. The two application objects
mirror the local/client driver streams; executor/container aggregation is not claimed.

Amazon EMR documents Step logs below `<cluster-id>/steps/<step-id>/` and YARN container logs below
`<cluster-id>/containers/`. It also documents that client-mode Spark driver output is available in
Step logs, while cluster-mode driver output belongs to the application master. Mystack implements
the observable paths that can be represented by its local/client runtime and labels the gap.

<!-- section: outcomes -->
## Success, failure, and cancellation

Publication runs after the local process exits or Step preparation fails, but before the resulting
terminal Step state becomes observable. Success, non-zero exit, missing artifacts, and user
cancellation therefore all produce the same object-name set when `LogUri` is valid. A preparation
failure has empty process streams and `process_started=false` in `controller` and the publication
record. A cancelled process records its actual non-zero signal exit; the EMR state machine remains
the authority for `CANCELLED` versus `FAILED`.

The local `<work_root>/<cluster-id>/<step-id>/log-publication.json` record has schema version 1 and
one of these statuses:

| Status | Meaning |
| --- | --- |
| `published` | Every Step and application object was uploaded; `published_keys` is complete |
| `failed` | Upload stopped; `published_keys`, error type, and repair evidence describe partial work |
| `skipped` | `LogUri` was omitted; no S3 log write was attempted |
| `pending` | The management API has no record yet, normally because the Step is still running |
| `unreadable` | The local record is malformed or cannot be read; the response includes a repair hint |

<!-- section: recovery -->
## Durable publication and restart recovery

Before a Step prepares Spark, Mystack atomically writes `execution-journal.json`. Terminal process
facts are committed there before S3 publication starts. `publication-request.json` is the durable
outbox and records `pending`, `publishing`, `retrying`, `failed`, or `published`, including the
attempt and deterministic object keys. Each `put_object` has a configured timeout; retries use
configured bounded exponential backoff and overwrite the same keys, so a partial attempt is safe
to repeat.

At EMR startup, a `running` journal becomes `interrupted`. Any terminal journal with `LogUri` whose
publication is not complete is replayed before new startup clusters are provisioned. The Console
can explore these journal-backed logs even though the old in-memory boto3 cluster is intentionally
not reconstructed. `emr.log_retention_seconds` removes only old terminal work directories with a
`published` or `skipped` publication record; failed publication evidence is retained.

Live reads do not follow files through an unbounded connection. The backend returns at most
`emr.live_log_chunk_bytes` from separate stdout/stderr byte offsets. EMR maps repeated reads
to standard `text/event-stream` events whose IDs are `<stdout-offset>:<stderr-offset>`. A browser
can reconnect with `Last-Event-ID` or explicit offsets. This extension follows the
[HTML Server-Sent Events protocol](https://html.spec.whatwg.org/multipage/server-sent-events.html);
it is not an Amazon EMR API.

<!-- section: boundaries -->
## Implementation and repair boundaries

- S3 layout, gzip payloads, and failure records: `mystack.emr.adapters.outbound.logs`
- Execution journal, retention, and startup replay: `mystack.emr.adapters.outbound.journal`
- Process capture and the publication call boundary: `mystack.emr.adapters.outbound.runtime`
- Console/API projection: `mystack.emr.adapters.inbound.management`
- SSE service adapter: `mystack.emr.adapters.inbound.log_stream`
- Runtime client ownership and close order: `mystack.emr.runtime` and `mystack.emr.app`
- boto3/LocalStack Docker proof: `tests/e2e/test_emr_spark.py`

If AWS changes its documented directory contract, update the focused log adapter, this document,
its unit tests, and the Docker E2E together. Do not move S3 concerns into the Domain, repository, or
AWS request mapper.

<!-- section: sources -->
## Official sources

- [Amazon EMR: View log files](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)
- [Amazon EMR: Debug a cluster](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html)
- [Amazon EMR: Submit Spark work](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)
- [Amazon EMR RunJobFlow API](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
