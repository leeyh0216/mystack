# 테스트 전략

한국어 | [English](testing.md)

## 계층

| 계층 | 목적 | 외부 runtime | Timeout 출처 |
| --- | --- | --- | --- |
| Unit | Domain 상태, codec, routing, 설정 | 없음 | `tests.unit_timeout_seconds` |
| Architecture | 안쪽 import와 bounded context | 없음 | unit timeout |
| Contract | boto3 직렬화, 응답, modeled error | API process | `tests.contract_timeout_seconds` |
| E2E | Public Proxy, LocalStack, EMR Spark, Glue Catalog, Hive/Iceberg | Docker | `tests.e2e_timeout_seconds` |

모든 pytest 실행은 thread 방식의 `pytest-timeout`을 사용해 hang 시 Python thread stack을 출력합니다. Spark/bootstrap adapter도 YAML의 서비스별 process timeout을 받습니다.

## Contract 규칙

- boto3는 public Proxy endpoint에만 연결합니다.
- 성공 결과와 modeled AWS error code, HTTP status, side effect를 함께 검증합니다.
- 구현된 모든 operation은 boto3 coverage가 필요합니다.
- Glue partition 중복은 [CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)에 따라 `AlreadyExistsException`을 반환해야 합니다.
- EMR 테스트는 고정 sleep이 아니라 설정 deadline까지 문서화된 상태를 poll하며 [EMR cluster lifecycle](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html)을 따릅니다.

## 실제 runtime E2E

- boto3 S3로 LocalStack에 bootstrap/application/input을 업로드합니다.
- boto3로 EMR 리소스를 생성하고 조회합니다.
- 설정된 deadline으로 기다리며 모든 실패 로그를 보존합니다.
- 실제 Python 및 Java JAR Spark 3.5.x application의 S3A output과 Step 상태, 실행 중
  subprocess 취소를 검증합니다. JAR 제출은 Spark 공식
  [`spark-submit --class` 계약](https://spark.apache.org/docs/3.5.4/submitting-applications.html)을 따릅니다.
- 구현된 EMR 13개와 Glue 22개 operation 전부를 public Proxy 경계로 검증하며, 같은
  재사용 Glue 시나리오를 Glue service 직접 경계에서도 실행합니다.
- boto3와 Spark Hive/Iceberg adapter로 Glue Catalog를 검증합니다.
- 현재 Iceberg 시나리오는 create, append, read, schema evolution을 검증합니다. Partition과 transaction은 목표 범위이며 [AWS Glue Iceberg 계약](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)을 따릅니다.

## 재현성

Lockfile, hash-locked container export, YAML runtime profile, immutable container-base digest,
botocore manifest, Spark checksum/version, Iceberg version은 모두 테스트 입력입니다. 어느
하나를 갱신해도 해당 manifest/profile 문서와 E2E 증거가 필요합니다. CI는 `uv.lock`과
다른 `requirements/*.txt` export를 거부하며 공식 [uv export 명령](https://docs.astral.sh/uv/reference/cli/#uv-export)을
사용합니다.

AWS의 [Hexagonal architecture 모범 사례](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)는 독립 core test와 E2E 자동화를 권장합니다.
