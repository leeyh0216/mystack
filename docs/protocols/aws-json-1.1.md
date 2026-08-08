<!-- doc-id: aws-json-1.1 -->
<!-- lang: en -->

[한국어](aws-json-1.1.ko.md) | [English](aws-json-1.1.md)

# EMR and Glue wire protocol analysis

<!-- section: sources -->
## Sources of truth

The implementation uses these sources in descending order:

1. AWS EMR and Glue API References for operation semantics, limits, states and errors.
2. The pinned official botocore service models for protocol metadata, operation/shape names, required members, enums and exception declarations.
3. AWS Signature Version 4 and SDK endpoint configuration documentation.
4. Local contract observations from AWS CLI and boto3 pointed at Mystack. The emulator never queries a real AWS account for comparison.

Relevant official references:

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [AWS Signature Version 4](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html)
- [Service-specific SDK endpoints](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Official botocore SDK models](https://github.com/boto/botocore/tree/develop/botocore/data)

<!-- section: metadata -->
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

<!-- section: request -->
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

Response forwarding buffers HTTPX's raw encoded stream rather than its decoded content. It retains
`Content-Encoding` and AWS checksum headers, drops only the non-HEAD `Content-Length` so the outward
server can calculate the encoded wire length, and preserves HEAD representation metadata. This is
required for boto/botocore to validate S3 gzip-object checksums. The implementation follows
[HTTPX raw streaming](https://www.python-httpx.org/async/#streaming-responses), [RFC 9110 hop-by-hop
fields](https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.1), and the
[S3 HeadObject contract](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html).

<!-- section: serialization -->
## Serialization rules

- Structures are JSON objects and lists are JSON arrays.
- Blob values are Base64 strings.
- The service model controls serialized member names; Python/boto naming conventions are not used at the wire boundary.
- Timestamps use the format specified by the shape/model. AWS JSON defaults apply when no shape override exists.
- An empty successful result is serialized as `{}` unless the operation model specifies another payload.
- The codec validates required members, primitive kinds, enums, list/map members and documented length/range/pattern constraints before invoking a use case.
- Unknown request members are rejected according to AWS JSON server behavior; botocore often rejects the same input client-side first.

After modeled input validation, dispatch uses explicit service operation families. EMR and Glue
each publish a reviewed implemented-operation set; a shared registry refuses duplicate family
ownership and any missing or unclassified handler. The union is contract-checked against the
exhaustive classification whose inventory comes from the official [botocore service
models](https://github.com/boto/botocore/tree/develop/botocore/data). Family selection does not add
a second wire parser or serializer.

Botocore's client `ParamValidator` supplies structural/type/length/range checks but does not
enforce every modeled enum or pattern. The server codec therefore walks the same pinned shapes
and adds those constraints. Patterns use the documented [Smithy pattern
semantics](https://smithy.io/2.0/spec/constraint-traits.html#pattern-trait), including the absence
of implicit anchors. A startup dialect audit rejects a future model pattern that the translation
layer cannot interpret and logs `shared/model.py` as the repair boundary. Validation logs contain
only shape paths and counts, never rejected values.

<!-- section: errors -->
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

<!-- section: sigv4 -->
## SigV4 behavior

Mystack accepts SDK-signed requests without validating the key or authorizing the caller. Service and
region may be extracted from the credential scope only as routing metadata. The proxy preserves the
original body and signature headers while forwarding, but no adapter may attach authentication or
authorization meaning to them. Keep the stack on a trusted local network.

<!-- section: emr -->
## EMR execution mapping

- `RunJobFlow` creates a cluster and enters `STARTING`.
- Bootstrap actions execute during `BOOTSTRAPPING`, before installed applications and steps are considered available. A non-zero bootstrap exit causes cluster failure/termination behavior.
- EMR `command-runner.jar` steps whose first argument is `spark-submit` map to a local `spark-submit --master local[*]` process.
- Step states progress through `PENDING`, `RUNNING` and a terminal state. `ActionOnFailure` controls queued-step and cluster behavior.
- S3 application/bootstrap URIs are downloaded through the configured LocalStack S3 endpoint. Data `s3://` URIs are exposed to Spark through S3A settings.

See the official [bootstrap action lifecycle](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html) and [Spark step mapping](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html).

<!-- section: glue -->
## Glue Catalog runtime mapping

Glue Job and JobRun APIs are out of scope. Spark interoperability uses a versioned Glue-compatible profile: Spark 3.5.4, Python 3.11, Java 17, and Iceberg 1.7.1. The test/runtime image derives from `public.ecr.aws/glue/aws-glue-libs:5`, which AWS documents for local Glue 5.0 development and testing.

- boto3 exercises the Glue Data Catalog API through the public proxy endpoint.
- Hive-compatible type strings are preserved; the Data Catalog does not validate type text.
- Spark Hive metastore and Iceberg catalog adapters point back to the emulator and LocalStack S3.
- boto3 contracts cover catalog CRUD, duplicate errors, partition CRUD/batches, type preservation,
  and table versions. The real Glue 5 E2E covers Hive complex types plus Iceberg
  create/append/read/schema evolution on LocalStack S3.

Mystack does **not** implement the Iceberg table format, manifests, snapshots, Spark extensions,
or an Iceberg wire protocol. The unmodified Apache Iceberg 1.7.1 `SparkCatalog`, AWS
`GlueCatalog`, and `S3FileIO` classes own those responsibilities. `GlueCatalog` sends ordinary
Glue Data Catalog AWS JSON 1.1 calls through Mystack, while Iceberg metadata and data files go to
LocalStack S3. This boundary follows the official [Iceberg AWS integration](https://iceberg.apache.org/docs/1.7.1/aws/).

See [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html), [the official Glue 5.0 Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), [Glue type systems](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html), and [Iceberg in Glue](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html).
