# EMR and Glue wire protocol analysis

## Sources of truth

The implementation uses these sources in descending order:

1. AWS EMR and Glue API References for operation semantics, limits, states and errors.
2. The pinned official botocore service models for protocol metadata, operation/shape names, required members, enums and exception declarations.
3. AWS Signature Version 4 and SDK endpoint configuration documentation.
4. Contract observations from AWS CLI and boto3. Optional real-AWS differential tests may refine message text, but cannot override documented behavior.

Relevant official references:

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [AWS Signature Version 4](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html)
- [Service-specific SDK endpoints](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Official botocore SDK models](https://github.com/boto/botocore/tree/develop/botocore/data)

## Service metadata

The pinned botocore model reports:

| Property | Amazon EMR | AWS Glue |
| --- | --- | --- |
| API version | `2009-03-31` | `2017-03-31` |
| Protocol | AWS JSON | AWS JSON |
| JSON version | `1.1` | `1.1` |
| Target prefix | `ElasticMapReduce` | `AWSGlue` |
| SigV4 service | `elasticmapreduce` | `glue` |
| Endpoint prefix | `elasticmapreduce` | `glue` |

## HTTP request contract

SDK requests use `POST /` with a JSON object body. The operation is selected by `X-Amz-Target`:

```http
POST / HTTP/1.1
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.CreatePartition
X-Amz-Date: 20260808T000000Z
Authorization: AWS4-HMAC-SHA256 Credential=test/20260808/ap-northeast-2/glue/aws4_request, ...

{"DatabaseName":"analytics","TableName":"events","PartitionInput":{"Values":["2026-08-08"]}}
```

The proxy resolves a service in this order:

1. known `X-Amz-Target` prefix;
2. SigV4 credential-scope service in `Authorization`;
3. AWS service hostname pattern;
4. LocalStack fallback.

Method, path, query string, request body, content type, authorization, tracing headers and custom metadata are forwarded. Hop-by-hop headers are removed. The byte body is never parsed and re-serialized by the proxy.

## Serialization rules

- Structures are JSON objects and lists are JSON arrays.
- Blob values are Base64 strings.
- The service model controls serialized member names; Python/boto naming conventions are not used at the wire boundary.
- Timestamps use the format specified by the shape/model. AWS JSON defaults apply when no shape override exists.
- An empty successful result is serialized as `{}` unless the operation model specifies another payload.
- The codec validates required members, primitive kinds, enums, list/map members and documented length/range/pattern constraints before invoking a use case.
- Unknown request members are rejected according to AWS JSON server behavior; botocore often rejects the same input client-side first.

## HTTP response and errors

Successful operations return the operation's modeled JSON output and HTTP 200. Responses include `Content-Type: application/x-amz-json-1.1` and `x-amzn-RequestId`.

Service errors carry all of the following so standard SDK parsers can materialize the modeled exception:

- documented HTTP status;
- `x-amzn-ErrorType` containing the exception code;
- `x-amzn-RequestId`;
- JSON error body with `__type` and the exception's modeled members, normally `Message`.

Example semantic contract for `CreatePartition`:

1. If the database or table is absent, return `EntityNotFoundException` with HTTP 400 and create nothing.
2. If the partition value tuple already exists, return `AlreadyExistsException` with HTTP 400 and leave the existing partition unchanged.
3. Otherwise create one partition and return HTTP 200 with `{}`.

This follows the [CreatePartition API errors](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html). It deliberately reproduces the service contract, not a Glue bug.

## SigV4 behavior

Development mode accepts SDK-signed requests without validating the key, matching common local AWS tooling. Strict mode validates the SigV4 structure and configured test credentials. Regardless of mode, service and region are extracted from the credential scope for routing and request context.

The proxy must not validate a signature and then mutate a signed component. Backends receive the original body and signature metadata; authentication policy belongs to the target adapter.

## EMR execution mapping

- `RunJobFlow` creates a cluster and enters `STARTING`.
- Bootstrap actions execute during `BOOTSTRAPPING`, before installed applications and steps are considered available. A non-zero bootstrap exit causes cluster failure/termination behavior.
- EMR `command-runner.jar` steps whose first argument is `spark-submit` map to a local `spark-submit --master local[*]` process.
- Step states progress through `PENDING`, `RUNNING` and a terminal state. `ActionOnFailure` controls queued-step and cluster behavior.
- S3 application/bootstrap URIs are downloaded through the configured LocalStack S3 endpoint. Data `s3://` URIs are exposed to Spark through S3A settings.

See the official [bootstrap action lifecycle](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html) and [Spark step mapping](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html).

## Glue runtime mapping

Glue version `5.0` maps to Spark 3.5.4, Python 3.11, Java 17 and Iceberg 1.7.1. The Glue Docker runtime derives from `public.ecr.aws/glue/aws-glue-libs:5`, the image AWS documents for local Glue 5.0 development and testing.

- `glueetl`/`gluestreaming` commands launch `spark-submit` with Glue libraries.
- `pythonshell` launches Python without Spark.
- default arguments are merged with per-run arguments using Glue precedence rules.
- Hive-compatible Data Catalog metadata and Iceberg catalog configuration point back to the emulator/LocalStack endpoint.

See [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html), [the official Glue 5.0 Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), [Glue type systems](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html), and [Iceberg in Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html).

