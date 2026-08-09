<!-- doc-id: ci -->
<!-- lang: ko -->

[한국어](ci.ko.md) | [English](ci.md)

# CI, 의존성, 릴리스 자동화

<!-- toc:start -->
## 목차

- [워크플로](#워크플로)
- [기여자가 바로 보는 테스트 보고서](#기여자가-바로-보는-테스트-보고서)
- [프런트엔드 테스트 격리](#프런트엔드-테스트-격리)
- [브랜치 보호 기준](#브랜치-보호-기준)
- [의존성 업데이트](#의존성-업데이트)
- [GHCR 게시](#ghcr-게시)
- [실패 진단과 게시 검증 정보](#실패-진단과-게시-검증-정보)
<!-- toc:end -->

<!-- section: workflows -->
## 워크플로

| 워크플로 | 실행 조건 | 계약 |
| --- | --- | --- |
| `ci.yml` | `main`/`develop`/`feature/*` push, PR, manual | Version 준비 상태, Python 3.11 계약, required case 표, 원본-free GHCR Compose 검증, frozen Dev Container build를 실행하고 `Required CI`로 결과 집계 |
| `model-drift.yml` | 주간, manual | 최신 botocore와 pinned 모델 비교, 실행 가능한 단일 issue 생성/갱신 |
| `e2e.yml` | 관련 PR, nightly, manual | 명시적 required boto3/AWS SDK for pandas/Spark/Hive/Iceberg case별 독립 Docker job과 Chromium console 접근성 E2E |
| `release.yml` → reusable `container-publish.yml` | `develop`/`main` 직접 push의 `CI` 성공 `workflow_run` | Snapshot 또는 정식 정책 판정, required 검증, 로컬 scan, 같은 SHA의 변경 불가 게시, 익명 검증, 정식 GitHub Release |
| `prepare-version-pr.yml` | manual | Version 파일 변경 branch와 `develop` 대상 PR 생성, package/tag/release 변경 없음 |

워크플로는 [GitHub Actions 공식 문서](https://docs.github.com/actions/writing-workflows)를 따릅니다. CI
제한 시간은 명시하며 로컬에서는 YAML 값을 사용합니다. Actions는 pytest 주석에서 생성한 무시되는
`ci-artifacts/compatibility/compatibility-evidence.json`의 `include` 항목만 읽고 클라이언트/실행
환경 전수 조합을 암묵적으로 만들지 않습니다. 원본 정책과 형식 지정 pytest 주석이 필수 입력입니다.
이 구성은 GitHub의 [공유 매트릭스
방식](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)을
따릅니다.
생성한 프로필의 `expected_duration_minutes`는 명시적인 바깥 작업 시간 상한입니다. 로컬에서
수집만 수행하는 생성기에는 별도의 `tests.compatibility_collection_timeout_seconds` 제한이 있고
테스트 본문을 실행하지 않습니다.
PR과 push는 `required`, manual 실행은 `preview`, 정기·manual E2E는 `nightly`를 추가합니다. 선택
lane을 비워도 항상 비어 있지 않은 required lane과 합치므로 유효합니다.
Dev Container job은 [공식 CLI](https://github.com/devcontainers/cli)의
`--frozen-lockfile`로 feature digest가 바뀌지 않았는지 확인하고 image를 끝까지 build합니다.

<!-- section: test-reports -->
## 기여자가 바로 보는 테스트 보고서

Python, 프런트엔드, 명시적 호환성, Docker 호환성, 브라우저 E2E 테스트 작업은 모두 실행기가
제공하는 JUnit XML을 작성합니다. 저장소의 렌더러는 내려받을 수 있는 `*-test-report` 산출물 하나에
다음 세 파일을 만듭니다.

| 파일 | 용도 |
| --- | --- |
| `junit.xml` | pytest와 Vitest 사이의 안정적인 교환 형식이며 도구가 읽는 결과 |
| `index.html` | 별도 서비스나 credential 없이 로컬에서 열 수 있는 작고 escape된 정적 보고서 |
| `summary.md` | suite/case, duration, pass/fail, skipped count를 짧게 보여 주며 GitHub Job Summary에도 추가되는 결과 |

실패한 JUnit case는 현재 GitHub job의 annotation으로 표시합니다. 많은 실패가 있어도 읽기 쉽도록
20개까지만 annotation을 만들고 나머지는 HTML 보고서에 표시합니다. Test command가 JUnit XML을
만들기 전에 멈추면 실패가 없었던 것처럼 보이지 않도록 보고서에 `incomplete`를 표시합니다.

[Spark CI](https://github.com/apache/spark/blob/master/.github/workflows/build_and_test.yml)처럼 모든 실행에는 구조화된 결과와 summary를 제공하고 상세 log는 실패 시에만 남깁니다. [Trino의 result-processing action](https://github.com/trinodb/trino/blob/master/.github/actions/process-test-results/action.yml)도 테스트 보고서를 보존하고 별도 확인 절차를 만들지 않고 현재 job에 annotation을 연결합니다.

일반 `*-test-report` 산출물의 보존 기간은 14일입니다. `service-ui-builds-<SHA>`는 이틀간 보존되는
내부 build 산출물이며 테스트 결과나 Docker image 산출물가 아닙니다. 부분 key restore를 사용하지 않는 exact-key
cache가 같은 호환 producer lane의 재build를 막습니다. manifest는 원본 SHA, platform, lock/config 입력, producer run,
bundle 파일 digest를 묶고 Python CI, Docker E2E, release preflight가 재사용 전
검증합니다. 산출물가 없으면 로컬 build로 전환합니다. 기존 테스트 deadline도 유지합니다. pytest는 선택된 YAML
제한 시간을 받고 Vitest는 설정된 테스트와 hook deadline을 받습니다.

CI는 pull request와 `main` 또는 `develop` push에서 실행합니다. 같은 feature branch revision에 frontend
producer lane이 두 번 생기는 것을 막습니다.

<!-- section: frontend-test-isolation -->
## 프런트엔드 테스트 격리

Root Vitest 설정은 각 테스트 파일 전에 `ui/tests/setup.ts`를 불러옵니다. 공유 setup은 Vitest
`afterEach` hook에서 React Testing Library `cleanup`을 호출하므로 render된 React tree가 jsdom 종료 전에
unmount됩니다. 이 동작은 테스트 harness에 두고 EMR 또는 Glue production component에는 테스트 전용
`window` guard를 추가하지 않습니다. 구현은 공식 [Vitest setup-file 안내](https://vitest.dev/config/setupfiles)와
[React Testing Library cleanup 안내](https://testing-library.com/docs/react-testing-library/setup/)를 따릅니다.

<!-- section: branch-protection -->
## 브랜치 보호 기준

[Version 안내](versioning.ko.md)의 repository rule을 사용합니다. `main`은 PR 전용, `develop`은 PR
우선이며 두 branch 모두 force push와 삭제를 거부하고 linear history 및 `Required CI`를 요구합니다.
Version 준비 job은 새 정식 미게시 version이 없는 `main` PR을 거부하고 반영된 SHA에서 다시
검사합니다. CI는 실 AWS account를 호출하지 않으며 cloud credential을 요구하지 않습니다.

<!-- section: dependencies -->
## 의존성 업데이트

Dependabot은 [공식 설정 방식](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates)으로 Python, GitHub Actions, Docker를 매주 확인합니다. boto3/botocore는 protocol과 클라이언트 직렬화를 함께 검토하도록 묶습니다.

AWS SDK 업데이트는 계약 manifest, API 작업 범위, 정확한 immutable 산출물, 생성된 한·영
근거와 boto3 계약가 모두 일치해야 완료됩니다.

Container dependency는 `uv.lock`에서 hash와 함께 export합니다. `make requirements`가 세
component 파일을 갱신하고 CI는 공식 [uv export 방식](https://docs.astral.sh/uv/reference/cli/#uv-export)으로
stale export를 거부합니다. 기본 image base는 mutable tag 대신 immutable multi-architecture
digest를 사용합니다.

<!-- section: publication -->
## GHCR 게시

전체 [Version과 branch 흐름](versioning.ko.md)과 [Public GHCR 이미지 운영
절차](container-release.ko.md)를 따릅니다. 게시 job은 repository의
일회성 `GITHUB_TOKEN`과 `packages: write`를 사용하며 AWS/GCP credential이나 registry secret이
없습니다. GitHub는 이 인증과 repository/package 자동 연결을 공식
[Container registry 안내](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)에
문서화합니다.

Workflow가 새 package를 처음 만들면 private이고 관리자가 공식 visibility 절차로 한 번 공개으로
전환합니다. Consumer는 그 공개 image를 익명으로 pull합니다. 게시 authorization과 소비
visibility는 서로 다른 제어입니다.

정식 및 snapshot tag는 워크플로 정책상 append-only이고 `latest`는 의도적으로 없습니다.
재실행은 같은 원본 SHA의 산출물만 이어서 처리합니다. Consumer는 검증된 OCI index digest를
고정하며 rollback은 과거 digest를 선택하고 registry 이력을 변경하지 않습니다.

<!-- section: artifacts -->
## 실패 진단과 게시 검증 정보

Compose/서비스/Spark log, optimizer-run 파일, 모델/API drift JSON은 실패한 job에서만 upload하고
7일 동안 보존합니다. 성공한 실행은 summary와 테스트 보고서에 집중하면서도 실패 시에는 수정에 필요한
component와 case 맥락을 남길 수 있습니다. 진단 log는 경계와 side effect event를 담되 secret을
포함하면 안 됩니다.

게시 워크플로는 검토한 수용 보고서를 별도로 14일 보존합니다. 테스트 선언 호환성 사례, 게시 수용
보고서, API 분류, 결정적인 Glue 오류 보고서가 대상입니다. 로컬 이미지 사전 검사 결과는 게시 승인을
위한 정보이며 사용자용 테스트 결과 산출물이 아닙니다.
