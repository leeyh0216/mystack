<!-- doc-id: protocols/glue-partition-batch-errors -->
<!-- lang: ko -->

[한국어](glue-partition-batch-errors.ko.md) | [English](glue-partition-batch-errors.md)

# Glue partition과 batch 오류 계약

이 문서는 Mystack이 구현한 partition operation 9개의 결정적인 동작을 정의합니다. 공개 AWS Glue
API 문서와 고정한 botocore model을 기준으로 합니다. 실 AWS 계정을 호출하는 시험이나 판단은
없습니다. Operation 목록의 단일 기준은 생성한 [Glue 오류
표](../compatibility/glue-errors.ko.generated.md)입니다.

<!-- section: layers -->
## 검증 계층과 첫 번째 오류

다음 순서에서 처음 실패한 조건이 요청을 중단합니다.

1. 공통 AWS JSON 1.1 경계가 필수 항목, JSON 자료형, pattern, enum을 검증합니다. Model에 있는
   문자열·목록·map·숫자의 최댓값도 모두 검증합니다.
2. 설정한 `OperationTimeoutException` 또는 `InternalServiceException`을 application과 repository
   호출 전에 주입합니다.
3. 이름, pagination token, segment 범위와 expression 문법을 mutation 없이 검증합니다.
4. 상위 table을 찾습니다. 그다음 partition value 수와 partition key 수를 비교합니다.
5. Operation에 필요하면 원본 partition과 목적지 충돌을 확인합니다.
6. Mutation batch는 요청 순서대로 항목을 처리합니다. 성공한 항목은 다음 항목을 시작하기 전에
   durable storage에 commit합니다.

AWS가 여러 오류 조건 사이의 우선순위를 공개하지 않은 경우에 적용하는 Mystack 내부 순서입니다.
문서화되지 않은 AWS 순서와 같다고 주장하지 않습니다.

<!-- section: operations -->
## 단일 operation 판단

| Operation | Wire 검증과 오류 주입 뒤의 application 순서 |
| --- | --- |
| `CreatePartition` | 상위 table → value 수 → tuple 중복 → durable save |
| `GetPartition` | 상위 table → value 수 → partition 조회 |
| `GetPartitions` | page token → segment → expression 문법 → 상위 table → expression/schema 결합 → filter/segment/page |
| `UpdatePartition` | 상위 table → 기존 value 수 → 원본 partition → 새 value 수 → 목적지 충돌 → durable save |
| `DeletePartition` | 상위 table → value 수 → partition 조회 → durable save |

중복 생성은 `AlreadyExistsException`을 반환합니다. 상위 resource나 원본 partition이 없으면
`EntityNotFoundException`을 반환합니다. Value 수, token, segment, expression, update 목적지가
잘못되면 `InvalidInputException`을 반환합니다. 실패한 candidate state는 공개하지 않습니다.

<!-- section: update -->
## Update와 Spark Hive rename

공개 [`UpdatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdatePartition.html)
문서는 `PartitionInput.Values`를 바꿀 수 없다고 설명합니다. 하지만 AWS가 관리하는 Glue Hive
client의 `renamePartition`은 이전 `PartitionValueList`와 새 partition value를
`UpdatePartition`에 전달합니다([고정한 client
코드](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/53d09f0c97edb913b02e00904b6620ea7468e8f5/aws-glue-datacatalog-spark-client/src/main/java/com/amazonaws/glue/catalog/metastore/AWSCatalogMetastoreClient.java#L1351-L1385),
[delegate
코드](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/blob/53d09f0c97edb913b02e00904b6620ea7468e8f5/aws-glue-datacatalog-client-common/src/main/java/com/amazonaws/glue/catalog/metastore/GlueMetastoreClientDelegate.java#L1814-L1822)).

Mystack은 공식 유지보수 client의 Spark/Hive rename 경로를 지원합니다. `Values`를 생략하면 기존
tuple을 유지합니다. 새 tuple이 이미 있으면 model에 있는 `InvalidInputException`을 반환합니다.
`UpdatePartition` API 문서와 고정 botocore operation model에는 `AlreadyExistsException`이 없기
때문입니다. 이 호환성 결정은 local contract와 CI 전용 Spark Hive DDL 시나리오에서 검증합니다.

<!-- section: batches -->
## Batch 순서와 부분 성공

모든 batch는 항목 처리 전에 상위 table을 확인합니다. 상위 table이 없으면 operation 수준의
`EntityNotFoundException`을 반환합니다. 항목 오류나 비어 있는 성공 응답으로 바꾸지 않습니다.

- `BatchCreatePartition`은 잘못된 항목과 이미 존재하는 항목을 `PartitionError`에 입력 순서대로
  기록합니다. 같은 tuple이 한 번 성공한 뒤 다음 항목에서 중복 오류가 날 수 있습니다.
- `BatchUpdatePartition`과 `BatchDeletePartition`은 항목별 `ErrorDetail`을 입력 순서대로
  기록합니다. 반복한 원본 key는 앞 항목의 결과가 반영된 상태에서 처리합니다.
- `BatchGetPartition`은 찾은 partition을 요청 순서대로 반환합니다. 반복 key도 유지합니다.
  반환하지 못한 유효한 key는 `UnprocessedKeys`에 요청 순서대로 기록합니다. 이 응답에는 항목 오류
  field가 없으므로 value 수가 잘못되면 전체 operation이 `InvalidInputException`으로 실패합니다.
- 항목 오류가 앞에서 성공한 항목을 rollback하지 않습니다. Persistence 실패는 operation 수준의
  `InternalServiceException`을 반환합니다. 실패 candidate는 rollback하고 앞의 durable entry는
  유지하며 뒤의 entry는 시도하지 않습니다.

응답 구조는 공식 [`BatchCreatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchCreatePartition.html),
[`BatchGetPartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchGetPartition.html),
[`BatchUpdatePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchUpdatePartition.html),
[`BatchDeletePartition`](https://docs.aws.amazon.com/glue/latest/webapi/API_BatchDeletePartition.html)
문서를 따릅니다.

<!-- section: maintenance -->
## Logging, 시험과 수정 위치

`glue.partition_batch.before`, `.item.failed`, `.after` event는 operation, 항목 수, 안전한 항목
index, failure type과 결과 수를 기록합니다. Partition value는 기록하지 않습니다. Expression의
parse, schema 결합, 평가, segment event도 fingerprint, 연산자 구조, type과 개수만 기록합니다.

Client 변경으로 호환성이 깨지면 다음 순서로 확인합니다.

1. `protocol.validation.failed`는 고정 model 또는 `shared/aws_protocol/model.py`의 공통 검증을
   확인하라는 뜻입니다.
2. `adapter.mapping_failure`는 `glue/adapters/inbound/aws_partition.py` 또는 `aws_batch.py`를
   확인하라는 뜻입니다.
3. Batch 항목과 순서는 `glue/application/batch.py`를 확인합니다. Value, update, 목록 순서는
   `glue/application/partition.py`와 immutable domain model을 확인합니다.
4. `persistence.side_effect_failed`는 repository transaction의 전·후·rollback event를 확인합니다.

빠른 contract는 `glue/tests/test_partition_batch_error_semantics.py`입니다. Public Proxy boto3,
Spark Hive, AWS SDK for pandas 경로는 CI에서만 실행하며 명시적인 timeout을 적용합니다.

<!-- section: exclusions -->
## 제외 범위

인증, 인가, IAM, Lake Formation, cross-account, cross-Region 동작, 실 AWS 비교, Glue Job과 Crawler는
이 계약의 범위가 아닙니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue partition API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [AWS Glue exception](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html)
- [AWS Glue `GetPartitions`](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [botocore Glue service model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
- [Apache Hive Metastore용 AWS Glue Data Catalog client](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore)
