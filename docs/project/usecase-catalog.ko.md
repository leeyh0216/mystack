<!-- doc-id: project-usecase-catalog -->
<!-- lang: ko -->

[한국어](usecase-catalog.ko.md) | [English](usecase-catalog.md)

# 구현 기반 사용 사례 목록

<!-- section: metadata -->
## Metadata와 범위

- 상태: approved
- 갱신일: 2026-08-09
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`
- 포함: HTTP endpoint, application operation, runtime process, management UI, release CLI/workflow
- 제외: process 내부 사용자 plugin, Glue Job/JobRun/Crawler
- 근거 우선순위: 코드 > test > commit/issue > 문서
- 공식 inventory: [botocore service model](https://github.com/boto/botocore/tree/develop/botocore/data)

<!-- section: uc-001 -->
## UC-001: AWS request routing

- 목적/actor/trigger: AWS CLI, boto3, 기타 SDK가 public Proxy로 HTTP를 보냅니다.
- 입력: 필수 method/path/body/header, 선택 query, YAML route registry. Target/signing/host claim
  중복과 형식을 시작 시 검증합니다.
- 출력: backend status, 안전한 header, raw response byte이며 저장 data/event는 없습니다.
- 부수효과: EMR, Glue, LocalStack 중 하나로 outbound HTTP 한 번을 보냅니다.
- 선행조건/규칙: target prefix → SigV4 signing service → host prefix → fallback; signed byte를
  재직렬화하지 않습니다.
- 실패: 시작 시 중복/잘못된 route, 실행 중 연결/명시적 request timeout.
- 관측: route 이유, backend, body size/hash, status, duration; authorization/body는 제외합니다.
- 근거: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/routing.py:32`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/forwarder.py:57`
- 신뢰도: High

<!-- section: uc-002 -->
## UC-002: AWS JSON 1.1 operation 실행

- 목적/actor/trigger: EMR/Glue inbound endpoint가 `X-Amz-Target` POST를 처리합니다.
- 입력: target과 JSON object 필수, SigV4 metadata 선택. Dispatch 전에 고정 입력 구조의
  required/type/enum/pattern을 검증합니다.
- 출력: modeled JSON 200 또는 AWS-compatible error body/status/header입니다.
- 부수효과: 명시적으로 등록된 built-in handler 하나를 정확히 한 번 실행합니다.
- 선행조건/규칙: 공식 recognized operation이며 recognized 미지원 operation은 501입니다.
- 등록 규칙: 각 handler는 service별 family 하나에 속하며 registry는 dispatcher 생성 전에 그
  합집합이 검토한 구현 범위와 정확히 같은지 확인합니다.
- 실패: unknown operation, serialization/validation, domain error, 보호된 internal error.
- 관측: service/operation/model fingerprint, input/output member, request ID, duration.
- 근거: `shared/src/mystack/aws_protocol/endpoint.py`,
  `shared/src/mystack/aws_protocol/operation_registry.py`,
  `emr/src/mystack/emr/adapters/inbound/aws.py`,
  `glue/src/mystack/glue/adapters/inbound/aws.py`
- 신뢰도: High

<!-- section: uc-003 -->
## UC-003: EMR cluster와 step 관리

- 목적/actor/trigger: boto3/CLI가 Proxy를 통해 구현된 EMR 13개 operation 중 하나를 호출합니다.
- 입력: cluster/step spec, ID, marker/page size, tag, cancel/terminate flag. 공식 데이터 구조, state invariant,
  marker 형식을 검증합니다.
- 출력: cluster/step description/list, ID, cancel status 또는 빈 modeled response입니다.
- 저장/변경: process-local cluster, step, tag, protection/visibility state와 timestamp입니다.
- 부수효과: 비동기 bootstrap/step driver를 schedule하며 cancel/terminate가 child process를 멈춥니다.
- 선행조건/규칙: 문서화된 state transition, failure action, cluster별 queue 정책.
- 실패: validation, not found, invalid state, termination protection, bad marker.
- 관측: transition, scheduling, process lifecycle, public boto3 contract/E2E.
- 책임: cluster command, Step command, query가 독립된 최소 port를 사용하며 비동기 runner와
  scheduling은 queue driver만 소유합니다.
- 근거: `emr/src/mystack/emr/application/cluster.py`,
  `emr/src/mystack/emr/application/step.py`, `emr/src/mystack/emr/application/queries.py`,
  `emr/src/mystack/emr/application/driver.py`
- 신뢰도: High

<!-- section: uc-004 -->
## UC-004: Bootstrap/Spark artifact 준비와 local 실행

- 목적/actor/trigger: EMR background driver가 bootstrap action 또는 제출된 Spark step을 시작합니다.
- 입력: S3/local URI, 명시적 arg vector, cluster/step ID, LocalStack endpoint/credential,
  Spark/JAR/Python 설정과 timeout.
- 출력: runtime exit code/reason, stdout/stderr log이며 Spark가 LocalStack S3 object를 쓸 수 있습니다.
- 저장/변경: work/log directory와 EMR state transition입니다.
- 부수효과: shell 없이 S3 download와 subprocess start/signal/kill/cleanup을 수행합니다.
- 선행조건/규칙: 허용 URI/scheme과 runner, 시작 전을 포함한 idempotent cancel. Runtime Build는
  background 작업을 시작하지 않고 Start가 scheduling을 활성화하며 Close가 설정 deadline으로
  task와 child를 cancel/await한 뒤 artifact를 닫습니다.
- 실패: artifact 없음, bootstrap 실패, process timeout/exit, cancel, 잘못된 application args.
- 관측: S3/process 전/후/실패 event, Python/JAR Spark S3A/cancel E2E.
- 근거: `emr/src/mystack/emr/runtime.py`,
  `emr/src/mystack/emr/adapters/outbound/runtime.py`,
  `emr/src/mystack/emr/adapters/outbound/system.py`
- 신뢰도: High

<!-- section: uc-005 -->
## UC-005: Glue database 관리

- 목적/actor/trigger: boto3/CLI가 Create/Get/List/Update/DeleteDatabase 또는 import status를 호출합니다.
- 입력: CatalogId, name, DatabaseInput, pagination token/page size; 공식 데이터 구조와 normalized non-empty
  name을 검증합니다.
- 출력: modeled database document/list/next token 또는 빈 response입니다.
- 저장/변경: JSON-backed database와 선택적 초기 default database입니다.
- 책임: `CatalogDatabase`가 normalized name과 방어적 document snapshot을 소유하고
  `DatabaseCommands`, `DatabaseQueries`, `CatalogInitializer`가 flow를 분리합니다.
- 부수효과: persist/fsync/atomic replacement 뒤 visible candidate publish.
- 선행조건/규칙: case-normalized key, uniqueness, child constraint, 직렬화한 candidate transaction,
  최대 크기가 정해진 pagination.
- 실패: AlreadyExists, EntityNotFound, InvalidInput, 잘못된 pagination token.
- 관측: transaction/persist 전·후·rollback·migration event, direct/public boto3 test,
  failure/cancellation/restart 주입 test.
- 근거: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/outbound/repository.py`
- 신뢰도: High

<!-- section: uc-006 -->
## UC-006: Glue table과 version 관리

- 목적/actor/trigger: boto3/CLI가 Create/Get/List/Update/DeleteTable 또는 GetTableVersion(s)를
  호출합니다.
- 입력: CatalogId, database/name, TableInput, expression/attribute, VersionId, SkipArchive, pagination.
- 출력: table/version document, list/next token 또는 빈 modeled response입니다.
- 저장/변경: current table, 단조 증가 version, 선택적 archive입니다.
- 책임: `CatalogTable`이 revision/archive/CAS를 소유하고 table command, query, version-query
  handler를 분리합니다.
- 부수효과: table rename, archived version, 하위 partition key를 하나의 candidate로 commit합니다.
  Iceberg update는 전달받은 `metadata_location`을 원자적으로 교체하며 Mystack이 Iceberg metadata
  format을 구현하거나 parse하지 않습니다. 실제 client E2E로 Iceberg가 소유한 partition/schema/
  sort/identifier evolution과 COW/MOR row-level commit이 이 무손실 pointer 경로에서 유지되는지
  확인합니다.
- 선행조건/규칙: database 존재, unique normalized name, optimistic version/archive 동작이며 같은
  state file을 공유하는 JSON-backed process는 설정된 상한이 있는 POSIX lock도 공유합니다.
- 실패: AlreadyExists, EntityNotFound, InvalidInput과 modeled `ConcurrentModificationException`으로
  변환하는 domain version mismatch이며 open-table-format input은 제외합니다.
- 관측: 안전한 Iceberg commit/version/conflict/persistence event, spawn process CAS test, COW/MOR
  snapshot 근거와 두 container 실제 Spark/Iceberg retry E2E입니다.
- 근거: `glue/src/mystack/glue/application/service.py`,
  `glue/tests/test_iceberg_commit.py`, `glue/tests/test_iceberg_evolution_catalog.py`,
  `glue/tests/test_iceberg_row_level_catalog.py`, `docs/protocols/glue-iceberg-row-level-dml.ko.md`
- 신뢰도: High

<!-- section: uc-007 -->
## UC-007: Glue partition과 batch result 관리

- 목적/actor/trigger: boto3/CLI가 Create/Get/List/Update/DeletePartition 또는 batch 4개 operation을
  호출합니다.
- 입력: Catalog/database/table, partition value/input, expression, segment, pagination/schema flag.
- 출력: Partition/list/batch document입니다. Mutation batch error는 항목별 결과입니다. 상위
  resource 부재와 `BatchGetPartition` value 수 오류는 전체 호출을 실패시킵니다. 찾지 못한 유효한
  get key는 `UnprocessedKeys`로 반환합니다.
- 저장/변경: catalog/database/table/value tuple key의 partition record입니다.
- 책임: `CatalogPartition`이 immutable value와 cardinality를 소유하고 command, query,
  부분 성공 batch handler를 분리합니다.
- 부수효과: 각 성공 entry mutation 뒤 candidate를 원자적으로 persist하고 publish합니다.
- 선행조건/규칙: 상위 table 사전 확인, value와 partition key 수 일치, 지원 predicate/segment,
  입력 순서 처리입니다. Spark Hive rename은 AWS 유지보수 Glue client의 `UpdatePartition` 경로를
  사용합니다.
- 실패: AlreadyExists, EntityNotFound, InvalidInput, item별 ErrorDetail.
- 관측: 값을 제외한 batch 전·항목·후와 expression 단계 log, 결정적 wire contract, Glue 22개 전체
  public Proxy E2E입니다.
- 근거: `glue/src/mystack/glue/application/service.py`,
  `glue/src/mystack/glue/adapters/inbound/aws.py`,
  `docs/protocols/glue-partition-batch-errors.ko.md`
- 신뢰도: High

<!-- section: uc-008 -->
## UC-008: Service resource와 EMR log 조회

- 목적/actor/trigger: operator/service 소유 UI가 direct 또는 Proxy를 통해 versioned management endpoint를 호출합니다.
- 입력: component/path, resource/log query, 설정된 page limit이며 management credential은 의도적으로 없습니다.
- 출력: EMR cluster/step/log read model 또는 Glue database/table/partition tree입니다.
- 저장/변경/event: resource mutation 없이 management access audit event만 있습니다.
- 부수효과: 공개 gateway path를 사용하면 Proxy가 internal management HTTP를 한 번 호출합니다. 제출·resolved Step argument vector는 인증 없는 local UI에 의도적으로 제공하지만 그 값을 구조화 log에 기록하지 않습니다.
- 선행조건/규칙: 알려진 component, 활성화한 endpoint, application API pagination, 신뢰하는 local-network 배포.
- 실패: 비활성 endpoint, unknown component/resource, internal timeout.
- 관측: management forwarding/component adapter log와 UI E2E.
- 근거: `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/app.py:122`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/emr/src/mystack/emr/app.py:134`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/glue/src/mystack/glue/app.py:120`
- 신뢰도: High

<!-- section: uc-009 -->
## UC-009: Thread/task stack 조회

- 목적/actor/trigger: operator/UI가 `/_mystack/diagnostics/threads` 또는 `/tasks`를 호출합니다.
- 입력: diagnostic kind와 설정된 stack frame limit이며 인증 입력은 의도적으로 없습니다.
- 출력: frame local을 제외한 thread/task metadata와 source stack line입니다.
- 저장/변경/event: resource mutation 없이 diagnostic access audit log만 있습니다.
- 선행조건/규칙: diagnostics 활성화와 신뢰하는 local-network 배포.
- 실패: disabled 또는 알 수 없는 diagnostic kind.
- 관측: access result, component, client, 명시적인 `authentication=disabled-by-design` 근거.
- 근거: `/Users/leeyh0216/Documents/project/ministack-enhanced/shared/src/mystack/aws_protocol/diagnostics.py:55`
- 신뢰도: High

<!-- section: uc-010 -->
## UC-010: Browser management console 운영

- 목적/actor/trigger: local operator가 Proxy의 `/_mystack/ui/emr/`, `/_mystack/ui/glue/` 또는 emulator direct `/_mystack/ui/`를 엽니다.
- 입력: cluster/Step form과 action, database/table/tab 선택, refresh, log stream control.
- 출력: 접근 가능한 lifecycle/status, log/publication 근거, Glue schema/partition metadata, route/stack view입니다.
- 저장/변경: browser 선택 상태를 유지합니다. Read는 management endpoint, EMR mutation은 public AWS endpoint와 기존 application use case를 사용합니다.
- 선행조건/규칙: 각 emulator가 자기 React/TypeScript application을 package하고 Proxy는 안정 path만 전달합니다. 공통 primitive와 Tailwind semantic token은 service 방향으로만 의존하며 설정 polling 주기, keyboard/ARIA tab 계약, array를 shell parsing하지 않는 규칙을 지킵니다.
- 실패: unavailable component/endpoint 또는 modeled AWS error는 secret 없이 표시하며 가능한 경우 AWS code/request ID를 보존합니다.
- 관측: Playwright cluster/Step/Glue/keyboard/browser E2E, protocol 경계 log와 screenshot.
- 근거: `ui/src/components.tsx`, `emr/ui/src/App.tsx`, `glue/ui/src/App.tsx`,
  `proxy/src/mystack/proxy/forwarder.py`, `tests/e2e/test_console_browser.py`
- 신뢰도: High

<!-- section: uc-011 -->
## UC-011: Public multi-platform image 게시와 검증

- 목적/actor/trigger: maintainer가 semantic tag를 push하거나 GHCR workflow를 수동 실행합니다.
- 입력: component/version과 파일 설정 package, Dockerfile, platform, Trivy version/policy, timeout.
- 출력: 익명으로 pull할 수 있는 public GHCR tag/digest, BuildKit SBOM/provenance, raw OCI index,
  scan/release artifact입니다.
- 저장/변경: GHCR package와 GitHub workflow artifact입니다.
- 부수효과: 게시자 token login, image build/push/pull, scanner DB/image download와 1회성 수동
  package visibility 전환입니다.
- 선행조건/규칙: 일회성 게시자 `GITHUB_TOKEN`, public consumer visibility, 새 tag, amd64+arm64
  index, `latest` 미사용.
- 실패: permission/tag collision, build/push, platform 검증, timeout, vulnerability policy.
- 관측: registry 전/후/실패 event와 upload evidence.
- 근거: `/Users/leeyh0216/Documents/project/ministack-enhanced/.github/workflows/container-publish.yml:1`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/scripts/registry_release.py:75`
- 신뢰도: 구현 High; 최초 remote 세 package 전체 성공은 아직 미확정.

<!-- section: uc-012 -->
## UC-012: AWS SDK for pandas data와 metadata 왕복

- 목적/actor/trigger: Python application이 AWS SDK for pandas 3.17.0으로 S3 Parquet dataset과
  Glue Catalog metadata를 함께 관리합니다.
- 입력: DataFrame, S3 dataset URI, database/table 이름, partition column과 boto3 session입니다.
- 출력: 기록한 object 경로, Glue type/table/partition, 다시 읽은 DataFrame입니다.
- 저장/변경: LocalStack S3의 partitioned Parquet object와 Glue emulator의 database/table/partition입니다.
- 부수효과: 모든 S3와 Glue 호출을 하나의 공개 Proxy endpoint로 보냅니다.
- 선행조건/규칙: `AWS_ENDPOINT_URL_S3`와 `AWS_ENDPOINT_URL_GLUE`를 같은 Proxy로 지정하며
  `HeadObject`의 representation `Content-Length`를 보존합니다.
- 실패: S3 metadata 손실, 지원하지 않는 Glue operation, Parquet data 손상, 명시적 E2E timeout입니다.
- 관측: Proxy route/forward 전·후·실패 event와 Glue operation/repository event를 남기며 test는
  생성한 resource를 정리합니다.
- 검증: partition 두 개의 write/read, Glue table type과 partition, S3
  [HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)를 확인합니다.
- 근거: `/Users/leeyh0216/Documents/project/ministack-enhanced/tests/e2e/test_awswrangler.py`,
  `/Users/leeyh0216/Documents/project/ministack-enhanced/proxy/src/mystack/proxy/forwarder.py`
- 신뢰도: High

<!-- section: uc-013 -->
## UC-013: 문서화된 Glue timeout 또는 internal failure 재현

- 목적/actor/trigger: Maintainer가 Glue emulator 시작 전에 YAML fault rule을 활성화하고 해당
  operation에 유효한 boto3/CLI 요청을 보냅니다.
- 입력: 고유 rule ID, 구현한 22개 operation 중 하나, `OperationTimeoutException` 또는
  `InternalServiceException`, response message입니다.
- 출력: 결정적인 code/status/message와 request ID가 있는 modeled AWS JSON error입니다.
- 저장/변경: 없으며 handler와 catalog repository를 호출하지 않습니다.
- 책임: Type이 있는 application policy가 설정 값을 보유하고 inbound `GlueFaultInjector`가 rule을
  선택하며 공통 controller가 wire serialization을 담당합니다.
- 부수효과: Configuration loading 뒤에는 없습니다.
- 선행조건/규칙: 공식 요청 구조/value 검증이 injection보다 먼저이며 operation마다 rule 하나만
  허용합니다. 인증·인가 오류와 알 수 없는 operation은 시작 시 거부합니다.
- 실패: 잘못된 설정은 service 시작을 막고 일치하지 않는 operation은 자연스러운 catalog 경로를
  따릅니다.
- 관측: `glue.error.decision`이 요청 값과 설정 response message 없이 condition/rule/phase/code와
  mutation 보장을 기록합니다.
- 근거: `contracts/glue-error-conditions.yaml`,
  `glue/src/mystack/glue/adapters/inbound/aws_faults.py`,
  `glue/tests/test_error_contracts.py`
- 신뢰도: High

<!-- section: uc-014 -->
## UC-014: 결정적인 Glue catalog 오류 판단 적용

- 목적/actor/trigger: boto3, Spark, AWS SDK for pandas client가 구현된 database, table,
  table-version, import-status operation 중 하나를 수행합니다.
- 입력: 공식 model 요청과 현재 local catalog 상태이며 version, projection, pagination, archive,
  설정 fault 값은 선택입니다.
- 출력: 성공 document 또는 첫 번째 결정적인 modeled validation/not-found/conflict/concurrency/system
  오류입니다.
- 저장/변경: 성공 mutation은 새 catalog revision 하나를 commit하고 실패 candidate는 visible/durable
  snapshot을 보존합니다.
- 책임: Inbound family는 wire 전용 projection, application aggregate는 resource 순서/archive/rename/
  cascade, repository는 atomic persistence, error boundary는 code를 담당합니다.
- 부수효과: 성공 mutation만 durable save를 수행하며 query와 자연 오류는 read-only입니다.
- 선행조건/규칙: Input → lookup, parent → destination conflict, conflict → stale version,
  durable commit → publication 순서이며 인증과 외부 federation 상태는 제외합니다.
- 실패: `InvalidInputException`, `EntityNotFoundException`, `AlreadyExistsException`,
  `ConcurrentModificationException`, 정제되거나 설정한 system 오류입니다.
- 관측: 요청 값 없이 operation boundary, condition ID, mutation 보장, transaction rollback,
  persistence 전·후·실패 event를 기록합니다.
- 근거: `docs/protocols/glue-database-table-errors.ko.md`,
  `glue/tests/test_database_table_error_semantics.py`,
  `contracts/glue-error-conditions.yaml`
- 신뢰도: High
