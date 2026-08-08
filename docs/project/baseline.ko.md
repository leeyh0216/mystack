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
- Composition root는 `proxy/src/mystack_proxy/app.py`, `emr/src/mystack_emr/app.py`,
  `glue/src/mystack_glue/app.py`입니다.
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
- Glue 확장은 `stable`, `application`, `unsafe`의 독립 SPI를 제공합니다. 검증된 operation call을
  우선순위 chain으로 합성하고 최종 성공 응답을 공식 botocore 출력 구조로 다시 검증합니다.
- 시작 단계는 mount된 wheel을 network와 dependency resolution 없이 설치하고 Python entry point로
  provider를 찾습니다. `unsafe`는 명시적 허용과 설치된 Mystack 정확한 버전이 필요합니다.
- 상호운용성은 Spark 3.5.4 + Java 17, Glue/Hive complex type과 S3 Parquet, Apache Iceberg 1.7.1
  create/append/read/schema evolution E2E를 포함합니다.
- 운영 기능은 resource/log console, route/thread/task 진단, authorization과 payload 내용을 제외한
  구조화 boundary log를 포함합니다.
- 배포는 Python 3.11/3.12 CI, nightly/manual Docker E2E, 모델/API 변경 검사, private GHCR
  multi-platform 게시, SBOM/provenance, OCI index 검증, Trivy 정책을 포함합니다.
- Extension Docker E2E는 실제 wheel 설치, 세 SPI context의 동일 Catalog 접근, 우선순위 합성,
  boto3의 `AlreadyExistsException`을 검증합니다.
- 최종 test inventory는 63개입니다. Fast suite는 56개 통과와 real-AWS opt-in 2개 skip,
  기본 Docker/browser/Spark/Hive/Iceberg E2E는 4개 통과와 extension 전용 1개 skip,
  별도 extension Docker E2E는 1개 통과입니다.

<!-- section: entry-points -->
## Entry point와 명령

- 실행 파일: `mystack-proxy`, `mystack-emr`, `mystack-glue`,
  `mystack-glue-extension-bootstrap`
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
- 확장 사용자는 접근 범위와 호환성 수준에 따라 세 Glue SPI를 선택합니다. Domain과 Application
  layer는 extension package를 알지 않고 composition root만 context를 구성합니다.

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

현재 확장은 신뢰할 수 있는 code를 Glue process 안에서 실행합니다. 별도 process 또는 remote
sidecar 격리는 아직 구현하지 않았습니다. 공통 operation chain은 다른 emulator에도 재사용할 수
있지만 EMR용 public SPI와 context는 별도 제품 결정 뒤에 추가합니다.

<!-- section: confirmations -->
## 순차 확인 기록

- 2026-08-08: 사용자가 A/B/C 세 수준을 모두 지원하고 각각 다른 SPI로 제공하기로 확정했습니다.
- A는 snapshot과 capability 중심 `stable`, B는 application 직접 접근, C는 exact-version
  `unsafe`로 반영했습니다.

<!-- section: next-sequence -->
## 다음 권장 순서

1. 실제 팀 extension을 `stable`로 작성하고 capability 누락을 수집합니다.
2. SPI v1 호환성 test 묶음을 독립 package로 제공할지 평가합니다.
3. 공통 chain의 운영 경험을 확인한 뒤 EMR과 다른 service의 public context를 별도 설계합니다.
