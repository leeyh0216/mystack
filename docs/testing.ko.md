<!-- doc-id: testing -->
<!-- lang: ko -->

[한국어](testing.ko.md) | [English](testing.md)

# 시험 전략

<!-- toc:start -->
## 목차

- [계층](#계층)
- [Contract 규칙](#contract-규칙)
- [실제 runtime E2E](#실제-runtime-e2e)
- [Upstream interoperability 매핑](#upstream-interoperability-매핑)
- [재현성](#재현성)
- [Local 호환성 기준](#local-호환성-기준)
<!-- toc:end -->

<!-- section: layers -->
## 계층

| 계층 | 목적 | 외부 runtime | Timeout 출처 |
| --- | --- | --- | --- |
| Unit | Domain 상태, codec, routing, 설정 | 없음 | `tests.unit_timeout_seconds` |
| Architecture | 안쪽 import와 도메인 경계 | 없음 | unit timeout |
| Frontend | 공통 theme/primitive, React component, TypeScript, production asset | Node/jsdom | `MYSTACK_FRONTEND_TEST_TIMEOUT_MS`와 CI job timeout |
| Contract | boto3 직렬화, 응답, modeled error | API process | `tests.contract_timeout_seconds` |
| E2E | Public Proxy, LocalStack, EMR Spark, Glue Catalog, Hive/Iceberg, AWS SDK for pandas | Docker | `tests.e2e_timeout_seconds` |

모든 pytest 실행은 thread 방식의 `pytest-timeout`을 사용해 hang 시 Python thread stack을 출력합니다. Spark/bootstrap adapter도 YAML의 서비스별 process timeout을 받습니다. Vitest는 test와 hook에 명시적으로 설정 가능한 millisecond deadline을 사용하며 CI는 lint, typecheck, test, production build 전체를 job timeout으로 한 번 더 제한합니다.

<!-- section: contracts -->
## Contract 규칙

- boto3는 public Proxy endpoint에만 연결합니다.
- 성공 결과와 modeled AWS error code, HTTP status, side effect를 함께 검증합니다.
- 구현된 모든 operation은 boto3 coverage가 필요합니다.
- Glue partition 중복은 [CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)에 따라 `AlreadyExistsException`을 반환해야 합니다.
- 하나의 boto3 중복 partition 계약에서 `stable`, `application`, `unsafe` context가 같은 관리
  상태를 조회하고 modeled error 변환 하나를 순서대로 합성하는지 확인합니다.
- EMR 테스트는 고정 sleep이 아니라 설정 deadline까지 문서화된 상태를 poll하며 [EMR cluster lifecycle](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-overview.html)을 따릅니다.
- EMR lifecycle test는 부분 startup과 driver 실패를 주입하고 scheduler를 두 번 닫으며 실제 child
  process를 실행해 역순 cleanup, task/process/lock 무누수, deadline 사용을 검증합니다. 책임 test는
  cluster-command, Step-command, query handler의 public surface도 고정합니다.
- Operation-family test는 service adapter 없이 모든 EMR·Glue family를 생성해 소유권이 겹치지
  않는지, 그 합집합이 구현 호환성 범위와 양방향으로 같은지, family-local modeled error 변환이
  유지되는지 확인합니다. 공통 registry mutation test는 중복·누락·예상 밖 handler를 request
  dispatch 전에 거부함을 검증합니다.

<!-- section: e2e -->
## 실제 runtime E2E

- boto3 S3로 LocalStack에 bootstrap/application/input을 업로드하고 bootstrap이 `hadoop`으로
  실행되어 `sudo`를 사용할 수 있는지, virtualenv를 만들고 뒤 PySpark Step이 그 interpreter를
  선택하는지 검증합니다.
- boto3로 EMR 리소스를 생성하고 조회합니다.
- Read-only versioned cluster file로 image를 시작하고 `RunJobFlow`를 호출하지 않은 상태에서 boto3와
  management 경계로 cluster를 찾습니다. EMR 재시작 뒤에는 새 ID 하나만 존재해야 합니다. Unit
  contract는 entry 하나가 잘못되면 command를 호출하기 전에 plan 전체를 거부합니다.
- Read-only pre-start overlay로 EMR을 시작해 일회용 CA를 OS/Python과 복사한 Java truststore에
  설치합니다. Lexical order와 export한 값이 PID 1, boto3로 만든 bootstrap action, 실제 Spark Step에
  전달되는지 검증합니다. 별도 raw-container contract는 즉시 실패 exit code 보존, 뒤 script 미실행,
  최종 UID 10001과 signal-safe PID 1 종료를 요구합니다. [Pre-start
  계약](protocols/emr/emr-prestart.ko.md)을 참고하세요.
- 설정된 deadline으로 기다리며 모든 실패 로그를 보존합니다.
- 실제 Python 및 Java JAR Spark 3.5.x application의 S3A output과 Step 상태, 주/dependency
  artifact materialize, 실행 중 subprocess 취소를 검증합니다. JAR 제출은 Spark 공식
  [`spark-submit --class` 계약](https://spark.apache.org/docs/3.5.4/submitting-applications.html)을 따릅니다.
- 성공, 준비 실패, 취소 Step이 정확한 gzip Step/application key 집합을 LocalStack S3에
  게시하는지 public Proxy로 검증하고 management API의 publication 증거와 일치하는지 확인합니다.
  배치는 [공식 EMR log 경로](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-debugging.html)를 따릅니다.
- 구현된 EMR 13개와 Glue 28개 operation 전부를 public Proxy 경계로 검증하며, 같은
  재사용 Glue 시나리오를 Glue service 직접 경계에서도 실행합니다.
- boto3와 Spark Hive/Iceberg adapter로 Glue Catalog를 검증합니다.
- boto3 `OpenTableFormatInput`으로 Iceberg v2 table을 생성하고 실제 GlueCatalog로 load/append한 뒤
  `UpdateOpenTableFormatInput`으로 evolve하고 다시 append합니다. 같은 Spark process에서 S3
  metadata도 확인합니다. Glue 공식
  [`CreateIcebergTableInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_CreateIcebergTableInput.html)과
  [내부 protocol](protocols/glue/glue-open-table-format.ko.md)을 기준으로 합니다.
- Glue state store의 실패·cancellation·같은 process 및 spawn process concurrent writer·stale table
  version·상한이 있는 file-lock contention·restart·rename/cascade·schema-1 migration을 주입합니다. 이
  계약은 Data Catalog metadata 원자성과 Iceberg catalog-pointer CAS를 검증하지만 Mystack이 Iceberg
  data/manifest/snapshot 기능을 구현한다는 뜻은 아닙니다.
- Glue domain 생성 전후 input/output dictionary를 변경해도 name, table revision/archive/CAS,
  partition cardinality, aggregate move가 immutable인지 확인합니다. 실행 가능한 책임 test는 각
  handler와 repository의 public method를 문서화된 범위로 제한합니다.
- AWS SDK for pandas 3.17.0으로 partitioned Parquet write/read, S3 HEAD, Glue table/partition을
  같은 공개 Proxy에서 검증합니다. 시험 범위는 [Client 호환성 표](compatibility/client-matrix.ko.md)에
  기록합니다.
- Managed Iceberg optimizer 세 유형을 공개 boto3 API와 실제 Glue 5 scheduler/Spark worker로
  검증합니다. CI는 각 run의 `work.json`, `stdout.log`, `stderr.log`를 Docker 진단 자료와 함께
  올립니다. AWS 공식 [table optimizer 안내](https://docs.aws.amazon.com/glue/latest/dg/table-optimizers.html)를
  기준으로 합니다.
- Playwright로 Proxy를 경유한 두 service 소유 React UI를 조작해 EMR cluster 생성·종료, Step 제출·추적·취소·조회,
  S3 log publication, 복합 Glue schema와 partition 탐색, keyboard/ARIA 동작과 깨끗한 browser
  console을 검증합니다. Browser action은 `tests.e2e.browser_action_timeout_seconds`를 사용하고
  CI는 설정된 환경변수 이름으로 Chromium 실행을 필수화합니다. Playwright 공식
  [auto-waiting 동작](https://playwright.dev/python/docs/actionability)도 이 명시적 deadline
  안에서만 사용합니다.
- 긴 Step 실행 중 EMR Compose service를 재시작한 뒤 recovered Console projection, 보존된 stdout,
  boto3 modeled not-found 동작, idempotent S3 archive 재게시를 검증합니다. Compose subprocess와
  모든 HTTP/SDK wait는 설정한 E2E timeout을 사용합니다. 주입한 lifecycle event는 Docker 공식
  [`compose restart` 계약](https://docs.docker.com/reference/cli/docker/compose/restart/)을 따릅니다.
- 현재 Iceberg scenario는 create, append, read, 검토한 모든 transform의 hidden partition
  evolution, top-level/nested schema evolution, sort/identifier evolution, dynamic overwrite,
  COW/MOR `UPDATE`/`DELETE`/`MERGE`, 실패한 merge의 snapshot 보존, time travel, branch/tag write,
  주요 metadata table, snapshot/maintenance procedure, 범위가 제한된 orphan cleanup, namespace 간
  rename, catalog-only drop, 추적 file purge와 서로 다른 Glue-image container의 barrier 동기화
  Spark writer 두 개를 검증합니다. Client가 stale `VersionId` commit을 refresh/retry하고 append
  둘을 모두 보존해야 합니다. [Iceberg snapshot/reference/procedure
  protocol](protocols/glue/glue-iceberg-snapshots-refs-procedures.ko.md), [Iceberg row-level DML
  protocol](protocols/glue/glue-iceberg-row-level-dml.ko.md), [Iceberg lifecycle
  protocol](protocols/glue/glue-iceberg-lifecycle.ko.md), [Open Table Format 입력
  protocol](protocols/glue/glue-open-table-format.ko.md), [Iceberg evolution
  protocol](protocols/glue/glue-iceberg-evolution.ko.md), [Iceberg commit
  protocol](protocols/glue/glue-iceberg-commits.ko.md), [AWS Glue Iceberg 계약](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html)을
  참고하세요.

<!-- section: upstream-mapping -->
## Upstream interoperability 매핑

Spark catalog E2E는 [AWS Glue Libraries](https://github.com/awslabs/aws-glue-libs)가 공개한 Glue 5
runtime profile(Spark 3.5.4, Python 3.11)을 따르며 Apache Iceberg Java 구현을 기준 integration으로
검증합니다. Catalog discovery 회귀는 생성 뒤 Spark SQL `SHOW TABLES`, `SHOW NAMESPACES`를 실행합니다.
즉 public Proxy가 직접 table handle뿐 아니라 Hive metastore와 Iceberg GlueCatalog의 발견 경로도
보존함을 증명합니다. Iceberg upstream project는 이 scenario에 쓰는 Spark module을 engine integration으로
정의합니다. 더 넓은 Trino/Flink/Hive integration은 이 프로젝트의 지원 주장 범위 밖입니다. [Iceberg
project module](https://github.com/apache/iceberg)을 참고합니다.

<!-- section: reproducibility -->
## 재현성

`uv.lock`, `package-lock.json`, hash-locked container export, YAML runtime profile, immutable container-base digest,
botocore manifest, Spark checksum/version, Iceberg version은 모두 테스트 입력입니다. 어느
하나를 갱신해도 해당 manifest/profile 문서와 E2E 증거가 필요합니다. CI는 `uv.lock`과
다른 `requirements/*.txt` export를 거부하며 공식 [uv export 명령](https://docs.astral.sh/uv/reference/cli/#uv-export)을
사용합니다.
Frontend 확인 절차는 ESLint, `tsc` project reference, Vitest, 두 Vite build를 실행합니다. 공통 theme
확인 절차는 두 application이 같은 semantic CSS variable을 사용함을 검증하고 Docker E2E는 각 최종
service image가 자기 build asset을 직접 제공하며 Proxy가 안정적인 path를 보존함을 검증합니다.

<!-- section: local-contracts -->
## Local 호환성 기준

Mystack은 동작 비교를 위해 실 AWS 계정을 호출하지 않습니다. 공식 AWS API 문서와 고정
botocore model이 operation, 데이터 구조, 제약, 선언된 오류를 정의합니다. 여러 잘못된 조건 중 무엇을
먼저 반환할지 문서가 정하지 않으면 검토한 내부 validation 순서로 최초 실패를 결정합니다.
Parameterized local contract가 Catalog 상태 오류를 모두 재현하고, 자연스러운 상태 조건이 없는
문서화된 internal/timeout 실패는 설정 기반 fault injection으로 재현합니다. 인증·인가 오류는
프로젝트 범위 밖입니다.
[Partition/batch 오류 계약](protocols/glue/glue-partition-batch-errors.ko.md)은 Docker를 시작하지 않고
model 최댓값, 검증 순서, 안정적인 부분 성공, `UnprocessedKeys`, persistence rollback을 검증합니다.

AWS의 [Hexagonal architecture 모범 사례](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)는 독립 core test와 E2E 자동화를 권장합니다.
