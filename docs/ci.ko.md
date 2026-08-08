# CI, dependency, release 자동화

한국어 | [English](ci.md)

## Workflow

| Workflow | Trigger | 계약 |
| --- | --- | --- |
| `ci.yml` | push, PR, manual | Python 3.11/3.12, lint, format, docs, model/requirements drift, Compose, unit/architecture/contract test, package |
| `model-drift.yml` | 주간, manual | 최신 botocore와 pinned model 비교, 실행 가능한 단일 issue 생성/갱신 |
| `e2e.yml` | 관련 PR, nightly, manual | Docker black-box boto3/Spark/Hive/Iceberg와 필수 Chromium console 접근성 E2E, 로그 보존 |
| `docker-publish.yml` | version tag, manual | immutable amd64/arm64 Proxy/EMR/Glue 게시, scan 증거, rollback retag |

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

## ECR 게시

전체 [private ECR 릴리스와 rollback runbook](ecr-release.ko.md)을 따릅니다. CloudFormation
stack은 immutable scan-on-push repository와 repository/environment로 제한된 OIDC role을
생성합니다. `AWS_ROLE_ARN`, `AWS_REGION`, `ECR_REGISTRY`를 `ecr-production` environment
variable로 설정합니다. GitHub는 OIDC token을 role로 교환하며 장기 AWS key를 저장하지 않습니다.
[공식 AWS OIDC 지침](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)을
참고하세요.

Version과 rollback tag는 append-only이며 `latest`는 의도적으로 없습니다. Production consumer는
검증된 OCI index digest를 고정합니다. Rollback은 과거 digest에 새로운 고유 tag를 연결하고
platform과 scan 검증을 다시 수행합니다.

## 실패 artifact

CI는 coverage, model drift, Docker log, test artifact를 항상 보존하려고 시도합니다. 로그는 component 경계와 side effect event를 담되 secret은 포함하지 않습니다.
