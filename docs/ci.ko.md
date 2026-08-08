# CI, dependency, release 자동화

한국어 | [English](ci.md)

## Workflow

| Workflow | Trigger | 계약 |
| --- | --- | --- |
| `ci.yml` | push, PR, manual | Python 3.11/3.12, lint, format, docs, model/requirements drift, Compose, unit/architecture/contract test, package |
| `model-drift.yml` | 주간, manual | 최신 botocore와 pinned model 비교, 실행 가능한 단일 issue 생성/갱신 |
| `e2e.yml` | 관련 PR, nightly, manual | Docker black-box boto3/Spark/Hive/Iceberg와 필수 Chromium console 접근성 E2E, 로그 보존 |
| `container-publish.yml` | version tag, manual | private GHCR amd64/arm64 게시, SBOM/provenance, OCI·Trivy 증거 |

Workflow는 [GitHub Actions 공식 문서](https://docs.github.com/actions/writing-workflows)를 따릅니다. CI timeout은 명시하며 local에서는 YAML 값을 사용합니다.

## Branch protection 기대값

Runtime 경로 변경에는 Python contract matrix와 Docker E2E를 필수로 합니다. Review된 PR, 해결된 대화, linear history를 요구합니다. 일반 CI에 real AWS credential은 필요하지 않습니다.

## Dependency update

Dependabot은 [공식 설정 방식](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates)으로 Python, GitHub Actions, Docker를 매주 확인합니다. boto3/botocore는 protocol과 client 직렬화를 함께 검토하도록 묶습니다.

AWS SDK 업데이트는 contract manifest, operation coverage, 한·영 문서, boto3 contract가 모두 일치해야 완료됩니다.

Container dependency는 `uv.lock`에서 hash와 함께 export합니다. `make requirements`가 세
component file을 갱신하고 CI는 공식 [uv export 방식](https://docs.astral.sh/uv/reference/cli/#uv-export)으로
stale export를 거부합니다. 기본 image base는 mutable tag 대신 immutable multi-architecture
digest를 사용합니다.

## GHCR 게시

전체 [private GHCR image runbook](container-release.ko.md)을 따릅니다. 게시 job은 repository의
일회성 `GITHUB_TOKEN`과 `packages: write`를 사용하며 AWS/GCP credential이나 registry secret이
없습니다. GitHub는 이 인증과 repository/package 자동 연결을 공식
[Container registry 안내](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)에
문서화합니다.

Version tag는 workflow 정책상 append-only이고 `latest`는 의도적으로 없습니다. Consumer는
검증된 OCI index digest를 고정합니다. Rollback은 과거의 검증된 digest를 선택하며 registry
이력을 변경하지 않습니다.

## 실패 artifact

CI는 coverage, model drift, Docker log, test artifact를 항상 보존하려고 시도합니다. 로그는 component 경계와 side effect event를 담되 secret은 포함하지 않습니다.
