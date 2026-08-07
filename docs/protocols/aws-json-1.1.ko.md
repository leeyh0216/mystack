# EMR과 Glue wire protocol 분석

한국어 | [English](aws-json-1.1.md)

## 기준 자료

구현 기준 우선순위는 다음과 같습니다.

1. operation 의미, 제한, 상태, 오류를 정의한 AWS EMR/Glue API Reference
2. protocol metadata, operation/shape, 필수 field, enum, exception을 정의한 고정 버전의 공식 botocore service model
3. AWS Signature Version 4와 SDK endpoint 설정 문서
4. AWS CLI/boto3 contract 관찰 결과

공식 자료:

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [AWS Signature Version 4](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html)
- [서비스별 SDK endpoint](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [공식 botocore SDK 모델](https://github.com/boto/botocore/tree/develop/botocore/data)

## 서비스 metadata

| 속성 | Amazon EMR | AWS Glue |
| --- | --- | --- |
| API version | `2009-03-31` | `2017-03-31` |
| Protocol | AWS JSON | AWS JSON |
| JSON version | `1.1` | `1.1` |
| Target prefix | `ElasticMapReduce` | `AWSGlue` |
| SigV4 service | `elasticmapreduce` | `glue` |
| Endpoint prefix | `elasticmapreduce` | `glue` |

## HTTP 요청 계약

SDK는 JSON object body와 `POST /`를 사용하며 `X-Amz-Target`으로 operation을 선택합니다.

```http
POST / HTTP/1.1
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.CreatePartition
Authorization: AWS4-HMAC-SHA256 Credential=test/20260808/ap-northeast-2/glue/aws4_request, ...

{"DatabaseName":"analytics","TableName":"events","PartitionInput":{"Values":["2026-08-08"]}}
```

Proxy는 target prefix, SigV4 credential scope, host pattern 순으로 route registry를 검색하고 일치하지 않으면 LocalStack으로 전달합니다. method, path, query, body byte, content type, authorization, tracing metadata를 보존하며 hop-by-hop header만 제거합니다.

## 직렬화와 검증

- structure는 JSON object, list는 JSON array입니다.
- blob은 Base64 string입니다.
- wire member name과 timestamp format은 service model을 따릅니다.
- 필수 member, primitive, enum, collection member, length/range/pattern을 use case 호출 전에 검증합니다.
- model fingerprint와 operation별 shape closure fingerprint를 기록하여 botocore 변경을 탐지합니다.

## 응답과 오류

성공 응답은 HTTP 200과 model output JSON을 반환합니다. 모든 응답은 `application/x-amz-json-1.1`과 `x-amzn-RequestId`를 포함합니다.

오류 응답은 문서화된 HTTP status, `x-amzn-ErrorType`, request ID, `__type`과 modeled member를 가진 JSON body를 반환합니다. 예를 들어 `CreatePartition`은 부모 database/table이 없으면 `EntityNotFoundException`, 동일 partition value tuple이 있으면 HTTP 400 `AlreadyExistsException`을 반환하고 기존 partition을 변경하지 않습니다. 기준은 [CreatePartition API](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)입니다.

## EMR 실행 mapping

- `RunJobFlow`는 `STARTING`에서 시작합니다.
- bootstrap action은 `BOOTSTRAPPING`에서 application/Step보다 먼저 실행합니다. non-zero exit는 문서화된 실패/종료 동작을 유발합니다.
- `command-runner.jar`의 첫 인자가 `spark-submit`이면 `spark-submit --master local[*]` 프로세스로 실행합니다.
- Step은 `PENDING`, `RUNNING`, terminal state로 진행하고 `ActionOnFailure`가 후속 Step/cluster 동작을 결정합니다.
- S3 application/bootstrap은 LocalStack S3에서 내려받고 data URI는 S3A 설정으로 접근합니다.

공식 기준: [bootstrap lifecycle](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html), [Spark Step](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-submit-step.html)

## Glue Catalog runtime mapping

Glue Job/JobRun은 범위 밖입니다. Spark 상호운용성 profile은 Spark 3.5.4, Python 3.11, Java 17, Iceberg 1.7.1이며 AWS의 `public.ecr.aws/glue/aws-glue-libs:5` 이미지를 test/runtime 기반으로 사용합니다.

- boto3가 public Proxy endpoint를 통해 Glue Data Catalog API를 검증합니다.
- Data Catalog가 type text를 검증하지 않는 공식 동작을 보존하면서 Hive 호환 type string을 저장합니다.
- Spark Hive metastore와 Iceberg catalog adapter는 emulator와 LocalStack S3를 사용합니다.
- boto3 contract는 catalog CRUD, 중복 오류, partition CRUD/batch, type 보존, table version을
  검증합니다. 실제 Glue 5 E2E는 Hive complex type과 LocalStack S3 기반 Iceberg
  create/append/read/schema evolution을 수행합니다.

공식 기준: [Glue 5.0 이미지](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), [Glue 타입 시스템](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html), [Glue Iceberg](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)
