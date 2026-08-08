<!-- doc-id: project-baseline -->
<!-- lang: ko -->

[한국어](baseline.ko.md) | [English](baseline.md)

# 프로젝트 기준선

<!-- section: metadata -->
## Metadata

- 상태: approved
- 소유자: leeyh0216
- 갱신일: 2026-08-08
- 저장소: private `leeyh0216/mystack`
- Scan root: `/Users/leeyh0216/Documents/project/ministack-enhanced`

<!-- section: purpose -->
## 목적과 실행 환경

Mystack은 Docker-first EMR·Glue Data Catalog protocol emulator입니다. 설정 기반 transparent
Proxy가 AWS SDK traffic을 독립 service container 또는 LocalStack으로 보냅니다. EMR은 실제
Spark 3.5.4 작업을 local에서 실행하고 Glue는 Catalog metadata를 저장하며 Spark, Hive, Apache
Iceberg와 연동합니다.

Glue Job, JobRun, Crawler API는 제외합니다. Glue 범위는 Data Catalog와 관측 가능한 AWS JSON
1.1 동작입니다. 공식 [EMR API](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)와
[Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)가 upstream 계약입니다.

<!-- section: facts -->
## 코드 기준 확정 사실

- Workspace module은 `shared`, `proxy`, `emr`, `glue`이며 개발 root를 제외하고 독립 package입니다.
- Composition root는 `proxy/src/mystack/proxy/app.py`, `emr/src/mystack/emr/app.py`,
  `glue/src/mystack/glue/app.py`입니다.
- 의존 방향은 Domain → Application port/use case → Adapter → composition root입니다. Architecture
  test가 내부 layer의 외부 module import를 거부합니다.
- Protocol 경계는 pinned botocore model, AWS JSON 1.1 입력 검증, modeled response/error, 명시적
  operation dispatch, model/API fingerprint를 제공합니다.
- Proxy는 YAML route registry의 target/signing/host 근거로 service를 찾고 service별 branch 없이
  알 수 없는 service를 LocalStack으로 보냅니다.
- EMR은 13개 operation, cluster/step state machine, LocalStack S3 bootstrap materialization,
  Python/JAR Spark 실행, 취소, log, management read model을 구현합니다.
- Glue는 database, table/version, partition/batch의 22개 operation을 구현합니다. JSON persistence는
  atomic replacement를 사용하고 inbound adapter가 domain error를 문서화된 오류로 변환합니다.
- 상호운용성은 Spark 3.5.4 + Java 17, Glue/Hive complex type과 S3 Parquet, Apache Iceberg 1.7.1
  create/append/read/schema evolution, AWS SDK for pandas 3.17.0 Parquet/Glue 왕복 E2E를 포함합니다.
- 운영 기능은 resource/log console, route/thread/task 진단, authorization과 payload 내용을 제외한
  구조화 boundary log를 포함합니다.
- 배포는 Python 3.11/3.12 CI, nightly/manual Docker E2E, 모델/API 변경 검사, private GHCR
  multi-platform 게시, SBOM/provenance, OCI index 검증, Trivy 정책을 포함합니다.
- 최종 test inventory는 58개입니다. Fast suite는 53개를 선택해 51개가 통과하고 real-AWS
  opt-in 비교 2개를 건너뜁니다. 기본 Docker/browser/Spark/Hive/Iceberg/AWS SDK for pandas E2E
  5개가 통과하며 두 명령 모두 설정된 명시적 timeout을 적용합니다.

<!-- section: entry-points -->
## Entry point와 명령

- 실행 파일: `mystack-proxy`, `mystack-emr`, `mystack-glue`
- 설정: `config/mystack.yaml`; release 설정: `config/registry-release.json`
- 설정 시작: `./scripts/bootstrap.sh`, `direnv allow`, 또는 제공된 Dev Container
- Fast 검증: `make test`, `make contract`, `make registry-check`, `make pre-commit`
- Runtime 검증: `make up`, `make e2e`, `make down`
- CI: `.github/workflows/ci.yml`, `e2e.yml`, `model-drift.yml`, `container-publish.yml`
- 구현 UseCase: [구현 기반 catalog](usecase-catalog.ko.md)

<!-- section: decisions -->
## 확정 아키텍처 결정

- 하위 module은 상위 module을 알 수 없습니다. Business abstraction은 shared wire package에
  들어가지 않습니다.
- 기존 AWS CLI/boto client는 하나의 public Proxy endpoint를 사용하고 service container는
  내부에 둡니다.
- 오류는 AWS bug가 아니라 문서화된 validation, code, status, state, side effect를 재현합니다.
- 모든 동작 문서는 한·영 pair와 직접적인 공식 출처를 가집니다.
- Side-effect 경계는 secret 없이 전/후/실패 event를 기록합니다.
- Test는 명시적 설정 가능 timeout을 사용하고 구현 operation은 public-Proxy boto3 E2E가 있습니다.
- Service별 동작은 담당 영역 안에 두며 process 내부 사용자 plugin API는 공개하지 않습니다.

이 규칙은 AWS [hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을
따릅니다.

<!-- section: consistency -->
## 정합성 결과

### 확정

- Architecture, 지원 범위, protocol, console, E2E, release 문서가 현재 코드와 일치합니다.
- Upstream 전체 분류는 미구현 operation을 compatible로 주장하지 않고 EMR 65개, Glue 299개를
  기록합니다.

### 수정한 drift

- 이전 baseline과 UseCase catalog는 이미 구현된 EMR, Glue, Spark/Iceberg, Docker E2E, UI,
  compatibility 생성을 미래 미지원 항목으로 기록했습니다. 이번 scan에서 오래된 주장을 교체했습니다.
- 이전 test 수는 현재 workspace가 아니라 초기 shared/Proxy 세로 경로를 설명했습니다.

### 미확정

- 최초 all-component GHCR 게시는 scan 도중 실행 중이었습니다. Workflow 구조는 구현됐지만 이
  baseline은 세 remote package의 최초 scan 성공을 주장하지 않습니다.

<!-- section: candidates -->
## 남은 후보 차이

새 emulator service는 설정 기반 Proxy route registry로 연결합니다. Service별 동작 변경은 담당
영역 안에서 일반 source 변경과 review 절차로 관리합니다.

<!-- section: confirmations -->
## 순차 확인 기록

- 2026-08-08: 사용자가 이전 A/B/C 설계를 폐기하고 process 내부 SPI를 완전히 제거하되 Proxy route
  확장성은 유지하기로 확정했습니다.

<!-- section: next-sequence -->
## 다음 권장 순서

1. Relative import를 포함한 architecture boundary를 자동 test로 강제합니다.
2. Glue state 변경을 transactional repository 경계 뒤로 옮깁니다.
3. Client와 runtime 호환성 검증을 versioned manifest에서 생성합니다.
