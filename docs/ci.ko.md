<!-- doc-id: ci -->
<!-- lang: ko -->

[한국어](ci.ko.md) | [English](ci.md)

# CI, 의존성, 릴리스 자동화

<!-- section: workflows -->
## Workflow

| Workflow | Trigger | 계약 |
| --- | --- | --- |
| `ci.yml` | `main`/`develop`/`feature/*` push, PR, manual | Version 준비 상태, Python 3.11/3.12 계약, required case matrix, source-free GHCR Compose 검증, frozen Dev Container build를 실행하고 `Required CI`로 결과 집계 |
| `model-drift.yml` | 주간, manual | 최신 botocore와 pinned model 비교, 실행 가능한 단일 issue 생성/갱신 |
| `e2e.yml` | 관련 PR, nightly, manual | 명시적 required boto3/AWS SDK for pandas/Spark/Hive/Iceberg case별 독립 Docker job과 Chromium console 접근성 E2E |
| `release.yml` → reusable `container-publish.yml` | `develop`/`main` 직접 push의 `CI` 성공 `workflow_run` | Snapshot 또는 정식 정책 판정, required 검증, local scan, 같은 SHA의 변경 불가 게시, 익명 검증, 정식 GitHub Release |
| `prepare-version-pr.yml` | manual | Version file 변경 branch와 `develop` 대상 PR 생성, package/tag/release 변경 없음 |

Workflow는 [GitHub Actions 공식 문서](https://docs.github.com/actions/writing-workflows)를 따릅니다. CI timeout은 명시하며 local에서는 YAML 값을 사용합니다.
Actions는 `contracts/compatibility-matrix.generated.json`에 생성된 `include` entry만 읽으며
client/runtime 전수 조합을 암묵적으로 만들지 않습니다. 이 구성은 GitHub의 [공유 matrix
방식](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)을
따릅니다.
PR과 push는 `required`, manual 실행은 `preview`, 정기·manual E2E는 `nightly`를 추가합니다. 선택
lane을 비워도 항상 비어 있지 않은 required lane과 합치므로 유효합니다.
Dev Container job은 [공식 CLI](https://github.com/devcontainers/cli)의
`--frozen-lockfile`로 feature digest가 바뀌지 않았는지 확인하고 image를 끝까지 build합니다.

<!-- section: branch-protection -->
## Branch protection 기대값

[Version 안내](versioning.ko.md)의 repository rule을 사용합니다. `main`은 PR 전용, `develop`은 PR
우선이며 두 branch 모두 force push와 삭제를 거부하고 linear history 및 `Required CI`를 요구합니다.
Version 준비 job은 새 정식 미게시 version이 없는 `main` PR을 거부하고 반영된 SHA에서 다시
검사합니다. CI는 실 AWS account를 호출하지 않으며 cloud credential을 요구하지 않습니다.

<!-- section: dependencies -->
## Dependency update

Dependabot은 [공식 설정 방식](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates)으로 Python, GitHub Actions, Docker를 매주 확인합니다. boto3/botocore는 protocol과 client 직렬화를 함께 검토하도록 묶습니다.

AWS SDK 업데이트는 contract manifest, operation coverage, 정확한 immutable artifact, 생성된 한·영
근거와 boto3 contract가 모두 일치해야 완료됩니다.

Container dependency는 `uv.lock`에서 hash와 함께 export합니다. `make requirements`가 세
component file을 갱신하고 CI는 공식 [uv export 방식](https://docs.astral.sh/uv/reference/cli/#uv-export)으로
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

Workflow가 새 package를 처음 만들면 private이고 관리자가 공식 visibility 절차로 한 번 public으로
전환합니다. Consumer는 그 public image를 익명으로 pull합니다. 게시 authorization과 소비
visibility는 서로 다른 제어입니다.

정식 및 snapshot tag는 workflow 정책상 append-only이고 `latest`는 의도적으로 없습니다.
재실행은 같은 source SHA의 artifact만 이어서 처리합니다. Consumer는 검증된 OCI index digest를
고정하며 rollback은 과거 digest를 선택하고 registry 이력을 변경하지 않습니다.

<!-- section: artifacts -->
## 실패 artifact

CI는 coverage, model drift, Docker log, test artifact를 항상 보존하려고 시도합니다. Release 검증
artifact에는 생성된 [release 수용 범위](compatibility/release-acceptance.ko.generated.md), compiled
matrix, API 분류, 결정적 Glue 오류 catalog도 보존합니다. 로그는 component 경계와 side effect
event를 담되 secret은 포함하지 않습니다.
