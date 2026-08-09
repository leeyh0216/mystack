<!-- doc-id: project-baseline -->
<!-- lang: ko -->

[한국어](baseline.ko.md) | [English](baseline.md)

# 프로젝트 기준선

<!-- toc:start -->
## 목차

- [Metadata](#metadata)
- [목적과 실행 환경](#목적과-실행-환경)
- [코드 기준 확정 사실](#코드-기준-확정-사실)
- [Entry point와 명령](#entry-point와-명령)
- [확정 아키텍처 결정](#확정-아키텍처-결정)
- [정합성 결과](#정합성-결과)
- [남은 후보 차이](#남은-후보-차이)
- [순차 확인 기록](#순차-확인-기록)
- [다음 권장 순서](#다음-권장-순서)
<!-- toc:end -->

<!-- section: metadata -->
## Metadata

- 상태: approved
- 소유자: leeyh0216
- 갱신일: 2026-08-10
- 저장소: 공개 `leeyh0216/mystack`
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`

<!-- section: purpose -->
## 목적과 실행 환경

Mystack은 Docker-first EMR·Glue Data Catalog protocol emulator입니다. 설정 기반 transparent
Proxy가 AWS SDK traffic을 독립 서비스 container 또는 LocalStack으로 보냅니다. EMR은 실제
Spark 3.5.4 작업을 로컬에서 실행하고 Glue는 Catalog 메타데이터를 저장하며 Spark, Hive, Apache
Iceberg와 연동합니다.

Glue Job, JobRun, Crawler API는 제외합니다. Glue 범위는 Data Catalog와 관측 가능한 AWS JSON
1.1 동작입니다. 공식 [EMR API](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)와
[Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)가 upstream 계약입니다.

<!-- section: facts -->
## 코드 기준 확정 사실

- Workspace module은 `shared`, `proxy`, `emr`, `glue`이며 개발 root를 제외하고 독립 package입니다.
- Composition root는 `proxy/src/mystack/proxy/app.py`, `emr/src/mystack/emr/app.py`,
  `glue/src/mystack/glue/app.py`입니다.
- 의존 방향은 Domain → Application port/use case → Adapter → composition root입니다. 실행 가능한
  계약이 relative import를 해석하고 바깥 방향·서비스 사이·어댑터 방향 사이의 의존성과 cycle을
  거부하며 mutation 테스트로 각 금지 방향을 확인합니다.
- Protocol 경계는 pinned botocore 모델, AWS JSON 1.1 입력 검증, modeled response/error, 명시적
  API 작업 dispatch, 모델/API fingerprint를 제공합니다.
- Inbound mapping은 EMR 5개와 Glue 5개 API 작업-family module을 shared registry로 합칩니다.
  Registry가 handler 중복·누락·미분류를 거부하며 구현 호환성 범위와 양방향으로 검사합니다.
- Proxy는 YAML route registry의 대상/signing/host 근거로 서비스를 찾고 서비스별 branch 없이
  알 수 없는 서비스를 LocalStack으로 보냅니다. Typed 실행 환경이 shared HTTP 클라이언트를 소유하고
  application state 내부 접근 없이 AWS request와 management forwarding capability를 분리해
  제공합니다.
- EMR은 13개 API 작업, cluster/step state machine, LocalStack S3 bootstrap materialization,
  Python/JAR Spark 실행, 취소, log, management read 모델을 구현합니다.
- EMR 책임은 최소 inbound Protocol 뒤에 focused cluster-command, Step-command, query, pagination,
  failure-policy, queue-driver component로 분리했습니다. Typed Build/Start/Close 실행 환경은 파일로
  설정한 shutdown deadline 안에서 scheduler task와 child process를 cancel/await하고 산출물를
  닫으며 driver lock을 해제합니다.
- Glue는 database, table/version, partition/batch/table-optimizer의 28개 API 작업을 구현합니다. Model 최댓값,
  자연 오류, batch 항목 순서와 rollback을 결정적으로 처리합니다. Source-built SQLite DB-API 실행 환경은
  카탈로그 초기화 전에 실행 가능 여부 확인 절차를 통과합니다. Normalized SQLite 카탈로그는 상한이 있는
  writer 재시도, WAL, transaction schema 초기화와 atomic database/table rename, cascade, VersionId
  check를 사용하며 inbound 어댑터는 domain error를 문서화된 오류로 변환합니다.
- Glue 책임은 immutable lossless domain snapshot이 name/revision/archive/partition invariant를,
  focused command/query/version/batch/pagination/initialization handler가 application policy를
  소유하도록 분리했습니다. 별도의 Open Table Format planner/orchestrator는 Iceberg v2 입력 검증,
  메타데이터-store 조정, 보상, 카탈로그 CAS를 소유하며 repository는 collection snapshot과 candidate
  transaction만 노출합니다. 이는 Glue 공식
  [`OpenTableFormatInput`](https://docs.aws.amazon.com/glue/latest/webapi/API_OpenTableFormatInput.html)을
  기준으로 합니다.
- 상호운용성은 Spark 3.5.4 + Java 17, Glue/Hive complex type과 S3 Parquet, Apache Iceberg 1.7.1
  Open Table Format create/update, create/append/read, dynamic overwrite, COW/MOR row-level DML,
  partition/schema/sort/identifier
  evolution, time travel, branch/tag write, 메타데이터/snapshot/maintenance procedure,
  rename/카탈로그-drop/추적 파일 purge, S3 orphan cleanup, concurrent `VersionId` commit retry,
  AWS SDK for pandas 3.17.0 Parquet/Glue 왕복 E2E를 포함합니다.
- 운영 기능은 EMR cluster/Step command와 Glue 메타데이터 탐색을 제공하는 서비스-aware Console,
  resource/log view, route/thread/task 진단, authorization과 payload 내용을 제외한 구조화 boundary
  log를 포함합니다. Console mutation은 boto3와 같은 공개 AWS 엔드포인트를 통과합니다.
- 배포는 하나의 안정된 `VERSION` 원천, `feature/*` → `develop` → `main`, Python 3.11 CI,
  nightly/manual Docker E2E, 모델/API 변경 검사, 변경 불가 develop snapshot과 main release,
  multi-platform GHCR image 게시, SBOM/provenance, OCI index 검증, Trivy 정책을 포함합니다.
- Test 정책상 fast suite는 실 AWS 비교 없이 전부 로컬에서 실행합니다. 별도
  Docker/browser/Spark/Hive/Iceberg/AWS SDK for pandas E2E lane은 CI가 소유합니다. 두 계층 모두
  설정된 명시적 제한 시간을 적용합니다.
- CI는 간결한 작업 요약과 내려받을 수 있는 HTML/JUnit 테스트 보고서를 게시합니다. 호환성 CI
  매트릭스와 검증 산출물은 테스트 본문을 실행하지 않는 형식 지정 pytest 주석 수집으로 만들고,
  무시되는 `ci-artifacts/compatibility/` 경로에 씁니다.

<!-- section: entry-points -->
## Entry point와 명령

- 실행 파일: `mystack-proxy`, `mystack-emr`, `mystack-glue`
- 설정: `config/runtime/mystack.yaml`; release/version 설정: `config/release/registry-release.json`,
  `config/release/version-files.json`, root `VERSION`
- 설정 시작: `./scripts/development/bootstrap.sh`, `direnv allow`, 또는 제공된 Dev Container
- Fast 검증: `make version-check`, `make architecture-check`, `make test`, `make contract`,
  `make registry-check`, `make pre-commit`
- Runtime 검증: `make up`, `make e2e`, `make down`
- CI: `.github/workflows/ci.yml`, `e2e.yml`, `model-drift.yml`, `release.yml`,
  `container-publish.yml`, `prepare-version-pr.yml`
- 구현 UseCase: [구현 기반 catalog](usecase-catalog.ko.md)

<!-- section: decisions -->
## 확정 아키텍처 결정

- 하위 module은 상위 module을 알 수 없습니다. Business abstraction은 shared wire package에
  들어가지 않습니다.
- 기존 AWS CLI/boto 클라이언트는 하나의 공개 Proxy 엔드포인트를 사용하고 서비스 container는
  내부에 둡니다.
- 오류는 AWS bug가 아니라 문서화된 유효성 검사, code, status, state, side effect를 재현합니다.
- 모든 동작 문서는 한·영 pair와 직접적인 공식 출처를 가집니다.
- Side-effect 경계는 secret 없이 전/후/실패 event를 기록합니다.
- Test는 명시적 설정 가능 제한 시간을 사용하고 구현 API 작업은 공개-Proxy boto3 E2E가 있습니다.
- Service별 동작은 담당 영역 안에 두며 process 내부 사용자 plugin API는 공개하지 않습니다.

이 규칙은 AWS [hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을
따릅니다.

<!-- section: consistency -->
## 정합성 결과

### 확정

- 소스와 CI 모두 `config/runtime/mystack.yaml` 및 계층화한 `scripts/` 경로를 사용합니다.
- 호환성 생성기는 무시되는 `ci-artifacts/compatibility/` 아래에 결과를 쓰며, CI는 호환성 작업을
  선택하기 전에 이 파일을 생성합니다.

### 수정한 drift

- 이전 baseline과 UseCase 카탈로그는 이미 구현된 EMR, Glue, Spark/Iceberg, Docker E2E, UI,
  compatibility 생성을 미래 미지원 항목으로 기록했습니다. 이번 scan에서 오래된 주장을 교체했습니다.
- 이전 테스트 수는 현재 workspace가 아니라 초기 shared/Proxy 세로 경로를 설명했습니다.
- 2026-08-09 문서·CI scan에서 공통 상단 index가 없는 Markdown 문서 92개, 사용자와 contributor
  내용 혼합, 최상위만 설명한 설정 leaf path 115개, 사람이 읽기 어려운 raw 테스트 진단을
  확인했습니다. Markdown-first navigation(#75)과 readable CI 보고서(#80)는 구현됐고 정적 site 결정은
  보류합니다.
- 호환성, 기여, CI, 지원 범위 문서는 원본 정책과 무시되는 CI/로컬 보고서를 구분하며, 제거한 커밋형
  생성 파일을 더 이상 링크하지 않습니다.

### 미확정

- 남아 있는 릴리스의 CI 완료와 게시 여부는 외부 워크플로 상태입니다.

<!-- section: candidates -->
## 남은 후보 차이

새 emulator 서비스는 설정 기반 Proxy route registry로 연결합니다. Service별 동작 변경은 담당
영역 안에서 일반 원본 변경과 review 절차로 관리합니다.

<!-- section: confirmations -->
## 순차 확인 기록

- 2026-08-08: 사용자가 이전 A/B/C 설계를 폐기하고 process 내부 SPI를 완전히 제거하되 Proxy route
  확장성은 유지하기로 확정했습니다.
- 2026-08-09: Spark, Trino, 저장소 문서·CI 구조를 검토한 뒤 사용자가 Markdown-first 사용자 문서
  재구성을 선택했습니다. 정적 문서 site는 나중에 결정합니다.

<!-- section: next-sequence -->
## 다음 권장 순서

1. 구현할 Glue와 EMR API 작업마다 문서화된 semantic, pagination, conflict, state-transition 계약를
   계속 확장합니다.
2. CI 보고서를 사용자 문서 탐색에서 제외하고 원본 정책을 바꿀 때 함께 갱신합니다.
3. 제품명, API 이름, 명령, 설정 키는 번역하지 않으면서 한국어 용어표를 적용합니다.
