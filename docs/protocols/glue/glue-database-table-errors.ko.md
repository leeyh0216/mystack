<!-- doc-id: protocols/glue/glue-database-table-errors -->
<!-- lang: ko -->

[한국어](glue-database-table-errors.ko.md) | [English](glue-database-table-errors.md)

# Glue database, table, version 오류 의미론

<!-- toc:start -->
## 목차

- [지원하는 판단](#지원하는-판단)
- [Archive, rename, delete 상태](#archive-rename-delete-상태)
- [System failure와 concurrency](#system-failure와-concurrency)
- [명시적 제외](#명시적-제외)
- [검증과 유지보수](#검증과-유지보수)
- [공식 출처](#공식-출처)
<!-- toc:end -->

Mystack은 아래 13개 database, table, table-version, import-status operation에 대해 결정적인 local
catalog 판단을 구현합니다. 고정한 botocore model이 public 요청 구조를 먼저 검증합니다. 저장된
schema가 필요하지 않은 application 값은 catalog 조회 전에 검증합니다. 이는 공개 문서에 근거한
내부 결정 순서이며 실 AWS 계정을 조회하지 않습니다.

<!-- section: decisions -->
## 지원하는 판단

| Operation | Model 검증 뒤의 결정적인 자연 오류 순서 |
| --- | --- |
| `CreateDatabase` | Candidate 이름 → database 중복 → durable save |
| `GetDatabase` | 이름 → database 존재 |
| `GetDatabases` | `AttributesToGet`/token/page size → 결과 page |
| `UpdateDatabase` | Source/candidate 이름 → source 존재 → destination 충돌 → durable save |
| `DeleteDatabase` | 이름 → database 존재 → atomic catalog cascade → durable save |
| `CreateTable` | Database/candidate 이름 → database 존재 → table 중복 → durable save |
| `GetTable` | Database/table 이름 → table 존재 |
| `GetTables` | Projection/expression/token/page size → database 존재 → 결과 page |
| `UpdateTable` | Source/candidate 이름과 숫자 `VersionId` → source 존재 → rename 충돌 → stale version → archive/mutation → durable save |
| `DeleteTable` | Database/table 이름 → table 존재 → atomic partition cascade → durable save |
| `GetTableVersion` | 이름과 숫자 version ID → table 존재 → version 존재 |
| `GetTableVersions` | 이름/token/page size → table 존재 → 결과 page |
| `GetCatalogImportStatus` | 성공 또는 설정한 timeout/internal failure |

잘못된 요청이나 실패한 candidate는 visible/durable state를 변경하지 않습니다. 중복 create와 rename
destination은 `AlreadyExistsException`, 없는 catalog resource는 `EntityNotFoundException`,
application 검증은 `InvalidInputException`입니다. Stale `UpdateTable.VersionId`는 공식
`UpdateTable` operation에 model된 `ConcurrentModificationException`입니다. 전역 Glue exception인
`VersionMismatchException`은 `UpdateTable` model 오류가 아니므로 이 operation에서 노출하지 않습니다.

<!-- section: state -->
## Archive, rename, delete 상태

Table은 version `0`에서 시작합니다. 기본 `UpdateTable`은 이전 current version을 archive하고 version
ID를 증가시킵니다. `SkipArchive=true`도 ID는 증가시키지만 교체한 version을 history에 추가하지
않습니다. Database rename은 table, table version, partition을 원자적으로 이동하고 table rename은
partition을 원자적으로 이동합니다. Rename 충돌은 stale version보다 먼저 판단합니다. Delete는 한
번의 local durable commit으로 database/table과 child를 접근 불가능하게 합니다. 문서화된 delete 후
가시성은 맞추지만 AWS의 비동기 orphan 정리 구현은 흉내 내지 않습니다.

`GetDatabases.AttributesToGet`은 `NAME` 또는 `NAME,TARGET_DATABASE`,
`GetTables.AttributesToGet`은 `NAME` 또는 `NAME,TABLE_TYPE`을 받습니다. Field를 주면서 빈 list이거나
`NAME`이 없으면 `InvalidInputException`입니다. Pagination token은 Mystack opaque token이며 잘못된
token은 resource 조회 전에 실패합니다.

<!-- section: system -->
## System failure와 concurrency

Persistence `OSError`는 repository가 candidate를 공개하지 않고 durable state를 유지한 뒤 정제된
`InternalServiceException`/HTTP 500이 됩니다. YAML fault rule은 application/repository 접근 전에
문서화된 `OperationTimeoutException` 또는 `InternalServiceException`을 재현합니다. 병렬 write는
직렬화합니다. 같은 명시적 version을 사용한 writer 둘은 하나가 성공하고 하나는
`ConcurrentModificationException`이 됩니다. `VersionId`가 없는 write는 각각 직렬화되어 authoritative
version을 증가시킵니다.

<!-- section: exclusions -->
## 명시적 제외

Federation, encryption, Lake Formation transaction/audit context, resource-link 접근,
cross-account/cross-Region, 인증·인가는 local trigger가 없고 범위 밖입니다. 이 release는 인위적인
catalog quota를 정의하지 않으므로 `ResourceNumberLimitExceededException`의 자연 trigger가 없습니다.
지원 catalog mutation에는 비동기 local resource 상태가 없으므로 `ResourceNotReadyException`을 만들지
않습니다. 설정 system fault는 timeout/internal만 다루며 제외한 상태를 가장하지 않습니다.

<!-- section: verification -->
## 검증과 유지보수

`glue/tests/test_database_table_error_semantics.py`는 parameterized AWS JSON boundary 계약을 실행하고
실패 operation 전후 durable store snapshot을 비교합니다. Projection, archive, rename, cascade,
persistence rollback도 검증합니다. 로컬에서는 설정 timeout으로 이 제한된 suite만 실행하고 public
Proxy/boto3 coverage는 CI가 담당합니다. 요청 구조/projection drift는 inbound operation family, 결정 순서
drift는 application aggregate, wire code drift는 `contracts/glue-error-conditions.yaml`을 수정합니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue database API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-databases.html)
- [AWS Glue table API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-tables.html)
- [UpdateTable](https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateTable.html)
- [GetTableVersion](https://docs.aws.amazon.com/glue/latest/webapi/API_GetTableVersion.html)
- [DeleteDatabase](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteDatabase.html)
- [DeleteTable](https://docs.aws.amazon.com/glue/latest/webapi/API_DeleteTable.html)
- [botocore Glue model](https://github.com/boto/botocore/tree/develop/botocore/data/glue)
