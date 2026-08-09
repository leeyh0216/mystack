<!-- doc-id: architecture -->
<!-- lang: ko -->

[한국어](architecture.ko.md) | [English](architecture.md)

# 아키텍처

<!-- toc:start -->
## 목차

- [목표](#목표)
- [시스템 경계](#시스템-경계)
- [의존성 규칙](#의존성-규칙)
- [실행 가능한 아키텍처 계약](#실행-가능한-아키텍처-계약)
- [실행 토폴로지](#실행-토폴로지)
- [호환성 전략](#호환성-전략)
- [로깅](#로깅)
- [저장과 실행](#저장과-실행)
- [비목표](#비목표)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: goals -->
## 목표

Mystack은 AWS API 경계에서 관찰되는 EMR 및 Glue Data Catalog 동작을 에뮬레이션하고 실제 Spark 작업을 로컬에서 실행합니다. 프로토콜, 상태 전이, 검증, 오류, 로그, side effect를 모두 계약으로 취급합니다.

<!-- section: boundaries -->
## 시스템 경계

| 컴포넌트 | 책임 | 알면 안 되는 것 |
| --- | --- | --- |
| `proxy` | AWS 서비스 판별과 HTTP 교환의 투명 전달 | EMR/Glue 도메인 규칙과 저장 방식 |
| `emr` | EMR 리소스, 클러스터/Step 상태 머신, bootstrap/Spark 실행 | Proxy 라우팅과 Glue 모델 |
| `glue` | Glue Data Catalog, Glue 타입, Hive/Iceberg 상호운용성 | Proxy 라우팅과 EMR 모델 |
| `shared` | AWS JSON 1.1 codec, 공식 서비스 모델, 요청 검증 | EMR/Glue 비즈니스 규칙 |
| `ui` | Service 중립 React primitive와 semantic Tailwind design token | EMR/Glue DTO, API, 비즈니스 규칙 |

Proxy route registry는 설정 기반입니다. 새 emulator는 대상 prefix, SigV4 signing name, host prefix, backend URL만 등록하며 Proxy 코드를 변경하거나 새 서비스 패키지를 import하지 않습니다.

Mystack은 process 내부 사용자 plugin API를 공개하지 않습니다. Service 동작 변경은 담당 영역
안에서 관리하고 새 AWS 서비스 emulator는 Proxy의 설정 기반 route registry로 연결합니다.
독립적으로 build한 distribution은 [ADR-0003](adr/0003-pep420-namespace-packages.ko.md)의 implicit
`mystack` namespace를 공유하며 어떤 distribution도 namespace root를 소유하지 않습니다.

<!-- section: dependencies -->
## 의존성 규칙

두 emulator 모두 다음 방향만 허용합니다.

```text
domain <- application <- adapters <- bootstrap / FastAPI app
```

- Domain: entity, value object, 상태 머신, domain exception
- Application: use case, orchestration, typed read/write port protocol; Domain과 내부에서 선언한
  port에만 의존
- Adapter: AWS JSON 입력, 저장소, S3, Spark/process 구현
- Composition root: concrete dependency와 FastAPI route 구성

CI의 architecture 테스트가 안쪽 계층에서 바깥 계층으로 향하는 import를 거부합니다. 이는 AWS의 [Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을 적용한 것입니다.

Glue Domain은 normalized `CatalogName`, 방어적으로 복사한 lossless `CatalogDocument` snapshot,
immutable database/table/partition value, table revision/archive/CAS, partition value 수 invariant를
소유합니다. Transport dictionary는 진입과 반환 시 복사하므로 어댑터나 caller가 committed
aggregate state를 변경할 수 없습니다. AWS 문서상 [Data Catalog가 type 문자열을 검증하지 않는
동작](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)을 유지하면서 모든 공식 field를
보존합니다.

Glue Application은 database command/query, table command/query, table-version query, partition
command/query, 부분 성공 partition batch, Open Table Format orchestration, pagination,
initialization handler로 책임을 나눕니다. Open Table Format domain planning은 storage와 무관하며
application handler가 주입받은 메타데이터-store port, 기존 table command, 고유 candidate, 보상,
`VersionId` CAS를 조정합니다. LocalStack 호환 S3 어댑터는 AWS [hexagonal architecture
지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)에
따라 composition root에서만 만듭니다. `CatalogApplication`은 inbound port를 위한 delegation 전용
compatibility facade입니다. Rename과 cascade policy는 이 handler가 소유합니다. Application 소유
read/write port는 immutable value와 scoped typed write transaction만 노출하며 mutable 카탈로그
aggregate, SQL, DB-API connection은 노출하지 않습니다.

Managed table optimizer는 전용 domain aggregate, command/query handler, executor port와 lifecycle
소유 scheduler를 추가합니다. Scheduler는 application facade를 통해서만 work를 claim하고
transition하며 outbound 어댑터는 Spark process/파일, Spark entrypoint는 Iceberg procedure를
소유합니다. [Optimizer protocol](protocols/glue/glue-table-optimizers.ko.md)과 AWS [table optimizer
API](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-table-optimizers.html)를 참고하세요.

EMR Application은 cluster command, Step command, read-only query, opaque pagination, queue
완료/실패 policy, 비동기 cluster driver를 분리합니다. Inbound 어댑터는 concrete facade가 아니라
각각의 최소 command/query Protocol을 선언합니다. Typed EMR 실행 환경은 작업을 시작하지 않은 상태로
build되고 FastAPI lifespan이 start한 뒤 scheduler task, bootstrap/Spark child process, S3 산출물
클라이언트 순서로 닫습니다. Close는 설정 deadline을 사용하고 여러 번 호출해도 안전하며, 각 실행 후
cluster별 driver lock을 제거합니다. 이 생명주기는 Python 공식 [task
cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)과 [async
subprocess](https://docs.python.org/3/library/asyncio-subprocess.html) 계약을 따릅니다.

Inbound AWS mapping은 API 작업 family별로 구성합니다. EMR은 cluster, Step, control, tag, query,
Glue는 database, table, version, partition, batch, table-optimizer family를 소유합니다. Shared 검증 registry가 이를
합치며 소유권 중복, 구현 API 작업 누락, 분류되지 않은 예상 밖 handler가 있으면 시작을
중단합니다. Registry는 공식 [botocore 서비스
모델](https://github.com/boto/botocore/tree/develop/botocore/data)에서 유도한 전체 호환성 분류와
양방향으로 검사합니다. Parsing과 output-모델 검증은 하나의 shared AWS JSON 엔드포인트에
그대로 둡니다.

<!-- section: enforcement -->
## 실행 가능한 아키텍처 계약

`make architecture-check`는 Python의 absolute import와 relative import를 해석하고 내부 module
graph를 구성한 다음 다음 의존성 변경을 실행 전에 거부합니다.

| 규칙 | 거부하는 의존성 |
| --- | --- |
| `shared-service-dependency` | 공통 wire 코드가 emulator 서비스를 import |
| `proxy-service-dependency` | Proxy가 route registry 대신 EMR 또는 Glue를 import |
| `cross-service-dependency` | EMR과 Glue가 서로를 import |
| `outward-dependency` | Domain/Application/Adapter가 더 바깥 layer를 import |
| `inner-transport-dependency` | Domain 또는 Application이 FastAPI, boto 등의 transport를 import |
| `composition-only-adapter` | Composition module이 아닌 곳에서 concrete 어댑터를 import |
| `adapter-sibling-dependency` | Inbound 어댑터와 outbound 어댑터가 서로를 import |
| `inbound-concrete-facade` | Inbound 어댑터가 concrete Application facade를 import |
| `service-import-cycle` | 내부 module 사이에 직간접 import cycle이 발생 |
| `inner-sqlite-driver-dependency` | Glue Domain/Application이 SQLite DB-API driver를 import |
| `inner-sql-execution` | Glue Domain/Application이 literal SQL statement를 실행 |
| `sqlite-adapter-domain-error-*` | SQLite 어댑터가 Glue domain error를 import 또는 raise |

Inbound 어댑터는 `application/use_cases.py`의 최소 Protocol과
`application/commands.py`의 immutable value에 의존합니다. Concrete 어댑터의 import와 생성은
`mystack.emr.app` 또는 `mystack.glue.app`에서만 허용합니다. 하나의 inbound 또는 outbound
어댑터 package 안의 import는 허용하지만 두 방향을 가로지르는 import는 거부합니다. 생성한
JSON과 Markdown은 Python 원본 root 밖에 있으며 검사에서 제외하는 생성 Python 파일은 없습니다.

각 금지 방향에는 위반 원본 파일을 주입하고 검사가 이를 거부하는지 확인하는 mutation 테스트가
있습니다. 실패 결과는 원본 path와 line, imported module, rule 식별자, 수정 안내를 함께
기록합니다. 구현은 Python의 [공식 relative import
규칙](https://docs.python.org/3/reference/import.html#package-relative-imports)을 따릅니다.

<!-- section: topology -->
## 실행 토폴로지

```text
host:4566 -> proxy:8080
                |-- ElasticMapReduce.* -> emr:8080
                |-- AWSGlue.*          -> glue:8080
                `-- 기타 모든 요청    -> localstack:4566
```

EMR은 emulated cluster별 Spark 로컬 process를 실행합니다. Glue managed optimizer scheduler는
outbound port를 통해 제한 시간이 있는 로컬 Glue 5 Spark process를 실행하지만 Glue Job/JobRun
실행은 아닙니다. Runtime process는 설정한 카탈로그/LocalStack 엔드포인트와 로컬 테스트 credential을
명시적 argument와 environment로 받습니다.

Management traffic은 별도 outward read-모델 경계를 사용합니다. 각 서비스의 inbound
management 어댑터가 Application/Domain resource를 versioned JSON으로 변환하고 각 emulator가
자기 React/TypeScript UI를 package하고 직접 제공합니다. Proxy는 안정적인 공개 UI path와 byte만
stream하며 서비스 asset이나 DTO를 소유하지 않습니다. 두 application은 서로 또는 서비스 내부를
import하지 않고 root `@mystack/ui` primitive와 중앙 Tailwind semantic token을 조립합니다. 자세한 내용은
[관리 Console 계약](console.ko.md)을 참고하세요.

UI command는 내부 객체 bridge로 이 architecture를 우회하지 않습니다. EMR mutation은
문서화된 AWS JSON 1.1 request를 공개 Proxy로 보내므로 boto3와 동일한 routing, 모델
유효성 검사, application handler, repository, error translation, 경계 logging을 거칩니다. Glue
탐색은 read 모델로 유지합니다. Static browser module은 이 두 outward 계약만 알기 때문에
Proxy와 browser code가 서비스 repository 또는 Domain object에 접근할 수 없습니다.

Proxy controller는 실행 환경 context가 제공하는 typed AWS request·management forwarding
capability에만 의존합니다. Runtime context는 하나의 shared HTTP pool을 소유하고 정상 종료와 일부
startup 실패에서 정확히 한 번 닫으며 FastAPI application state로 클라이언트를 노출하지 않습니다.
Route detection은 설정 기반 detector가 구현하는 Protocol입니다. 이 lifecycle은 HTTPX의 [공식
클라이언트 안내](https://www.python-httpx.org/advanced/clients/#opening-and-closing-clients)를 따릅니다.

<!-- section: compatibility -->
## 호환성 전략

1. 작업, 요청과 응답 구조, 열거형, 예외의 기준이 되는 공식 botocore 모델 버전을 고정합니다.
2. 전체 모델과 API 작업별 fingerprint를 계약 manifest에 기록합니다.
3. boto3/AWS CLI로 실제 엔드포인트 직렬화 계약을 테스트합니다.
4. 상태와 오류 의미론을 별도 계약 테스트로 검증합니다.
5. AWS가 문서화하지 않은 유효성 검사 우선순위는 검토한 로컬 계약로 정의해 결정적으로 유지하며 실 AWS 계정과 비교하지 않습니다.
6. 최신 botocore와의 차이를 매주 검사하고 변경 API 작업과 수정 위치를 이슈로 보고합니다.
7. Spark/Hive/Iceberg 조합은 실행 환경 프로필별 E2E 표로 검증합니다.

호환 오류란 문서화된 exception type, HTTP status, error code, 관련 message field, side effect 유무가 일치함을 뜻하며 AWS의 미문서화 버그를 재현한다는 뜻이 아닙니다.

<!-- section: logging -->
## 로깅

Controller 진입/종료, route 판정, 상태 전이, 저장소/S3/process side effect 전후와 오류를 구조화 JSON으로 기록합니다. Authorization과 payload 원문은 제외하고 request ID, API 작업, 모델 버전/fingerprint, payload 길이/해시, duration, 상태를 기록합니다. 모델 불일치 로그에는 수정할 어댑터와 문서를 가리키는 `fix_hint`를 포함합니다.

<!-- section: persistence -->
## 저장과 실행

Glue는 `glue.sqlite.database_file`로 선택한 정규화 SQLite 카탈로그 하나를 사용합니다. JSON state,
production in-memory store, migration fallback은 없습니다. Runtime 검증이 schema 생성보다 먼저
성공합니다. Application은 유효성 검사/error precedence와 typed port API 작업 선택을 소유하고,
outbound 어댑터는 connection, SQL, foreign key, commit/rollback을 소유합니다.

```text
AWS JSON request
      |
inbound Glue adapter
      |
application command/query ---- CatalogReadPort ----> short read connection
      |                         CatalogWritePort
      |                                |
      +---- domain validation -> scoped CatalogTransaction
                                       |
                                BEGIN IMMEDIATE
                                       |
                       normalized SQLite row + foreign-key cascade
                                       |
                        conditional VersionId update / COMMIT
```

Writer는 짧은 `BEGIN IMMEDIATE` transaction에서 조건부 `VersionId` update, archive/child row 기록,
진단용 카탈로그 revision 증가, commit 순서로 실행합니다. Persistence 실패는 transaction 전체를
rollback합니다. 진행 중인 commit은 cancellation으로부터 보호한 뒤 durable 결과를 반환합니다. 검증한
기본값은 WAL이고 rollback journaling은 명시적으로만 선택합니다. EMR cluster state는 현재
process-로컬입니다. Inbound startup-파일 어댑터는
side effect 전에 versioned `RunJobFlow` plan 전체를 검증하고
`CreateCluster` command로 mapping한 뒤 queue driver 시작 후 기존 Application port를 호출합니다.
Repository를 알거나 직접 변경하지 않습니다. Container 재시작 시 새 process-로컬 ID가 생깁니다.
자세한 계약은 [시작 클러스터 protocol](protocols/emr/emr-startup-clusters.ko.md)에 있습니다.
Lifecycle이 소유한 outbound log publisher가 terminal 로컬 Spark process stream을 문서화된
EMR Step S3 배치에 투영합니다.
Application/container ID는 synthetic임을 명시하고 게시 실패는 aggregate 밖에 기록해
RuntimeResult를 바꾸지 않습니다. S3 주 application과 Spark
dependency option은 path-style LocalStack용 object-store 어댑터가 materialize합니다. Spark는
shell 없이 명시적 argument vector로 실행합니다. Bootstrap script는 `hadoop`과 선택적 `sudo`로
Proxy가 아닌 EMR container 경계 안에서만 실행합니다. File은 뒤 Step까지 남지만 shell activation
상태는 subprocess 사이에 전달되지 않습니다. 선택적 EMR pre-start entrypoint는 Domain과
Application 밖의 별도 신뢰 배포 경계입니다. 운영자 파일을 검사해 root로 원본한 뒤 고정 standard
library 어댑터가 group/GID/UID를 바꾸고 PID 1을 `hadoop`으로 exec합니다. Hook 객체나 plugin
interface는 서비스 의존성 graph에 들어가지 않습니다. [Pre-start
계약](protocols/emr/emr-prestart.ko.md)을 참고하세요. Python의
[os.replace](https://docs.python.org/3/library/os.html#os.replace)와
[os.fsync](https://docs.python.org/3/library/os.html#os.fsync)를 사용합니다.

<!-- section: non-goals -->
## 비목표

- Glue Job과 JobRun
- Glue Crawler
- 초기 실행 환경에서 분산 EC2/YARN/HDFS의 물리적 재현
- 인증, 인가, IAM 또는 Lake Formation policy 평가
- Cross-account 또는 cross-Region 권한·routing 의미론
- 실 AWS 비교 테스트 또는 cloud credential 요구
- 미문서화된 AWS 버그 재현

<!-- section: sources -->
## 공식 참고 자료

- [AWS Prescriptive Guidance: Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
- [AWS Prescriptive Guidance: 테스트와 CI 모범 사례](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)
- [AWS SDK endpoint 설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Python 언어 참고서: package relative import](https://docs.python.org/3/reference/import.html#package-relative-imports)
- [Python 표준 라이브러리: fsync](https://docs.python.org/3/library/os.html#os.fsync)
- [AWS Glue type](https://docs.aws.amazon.com/glue/latest/dg/glue-types.html)
