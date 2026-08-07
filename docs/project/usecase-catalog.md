# Implementation-derived UseCase catalog

[한국어](usecase-catalog.ko.md) | English

## Metadata and evidence policy

- Status: approved and continuously maintained
- Evidence priority: code > tests > commits/issues > design documents
- Official protocol inventory: [botocore service models](https://github.com/boto/botocore/tree/develop/botocore/data)

## UC-001: Route an AWS request

- Actor: AWS CLI, boto3, or another AWS SDK
- Trigger: HTTP request to the public Proxy endpoint
- Input: method, path/query, byte body, headers; route registry from YAML
- Validation: unique route names and target/signing/host claims
- Output: byte response from EMR, Glue, or LocalStack backend
- Side effects: one outbound HTTP request
- Rules: target prefix, SigV4 signing name, host prefix, then fallback; signed body is not reserialized
- Failures: invalid route configuration at startup; backend connection/timeout at request time
- Observability: route evidence, backend origin, payload byte count/fingerprint, status, duration
- Evidence: `proxy/src/mystack_proxy/routing.py`, `forwarder.py`, `proxy/tests`
- Confidence: High

## UC-002: Process an AWS JSON 1.1 operation

- Actor: EMR or Glue inbound adapter
- Trigger: POST request with `X-Amz-Target`
- Input: service model, target header, JSON object, SigV4 metadata
- Validation: official model required/type/enum/constraint validation
- Output: HTTP 200 modeled JSON or SDK-compatible modeled error
- Side effects: dispatches exactly one registered application use case
- Failures: unknown target, serialization failure, invalid input, domain service error, internal error
- Observability: service/API/model fingerprint, operation/input shape, request ID, fix hint
- Evidence: `shared/src/mystack_aws_protocol/endpoint.py`, `model.py`, `shared/tests`
- Confidence: High

## UC-003: Inspect process thread/task stacks

- Actor: local operator or management UI
- Trigger: GET `/_mystack/diagnostics/threads` or `/tasks`
- Input: optional Bearer management token and configured stack limit
- Output: thread/task metadata and source stack lines; never frame locals
- Side effects: diagnostic access audit log
- Failures: diagnostics disabled or invalid token
- Evidence: `shared/src/mystack_aws_protocol/diagnostics.py`
- Confidence: High

## Candidate gaps

- EMR cluster/Step lifecycle and all boto3 control-plane contracts
- EMR bootstrap and real Spark 3.5.x local execution through LocalStack S3
- Glue Data Catalog database/table/version/partition/UDF semantics and errors
- Hive and Iceberg Spark interoperability
- Docker E2E and AWS-console-inspired UI

Glue Job, JobRun, and Crawler are explicitly not planned. See the [support scope](../support-scope.md) and [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html).

