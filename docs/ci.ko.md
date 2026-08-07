# CI, dependency, release 자동화

한국어 | [English](ci.md)

## Workflow

| Workflow | Trigger | 계약 |
| --- | --- | --- |
| `ci.yml` | push, PR, manual | Python 3.11/3.12, lint, format, docs, model manifest, unit/architecture/contract test, package |
| `model-drift.yml` | 주간, manual | 최신 botocore와 pinned model 비교, 실행 가능한 단일 issue 생성/갱신 |
| `e2e.yml` | 관련 PR, nightly, manual | Docker black-box boto3/Spark/Hive/Iceberg 테스트와 로그 보존 |
| `docker-publish.yml` | version tag, manual | amd64/arm64 Proxy/EMR/Glue image, provenance, SBOM, private ECR push |

Workflow는 [GitHub Actions 공식 문서](https://docs.github.com/actions/writing-workflows)를 따릅니다. CI timeout은 명시하며 local에서는 YAML 값을 사용합니다.

## Branch protection 기대값

Runtime 경로 변경에는 Python contract matrix와 Docker E2E를 필수로 합니다. Review된 PR, 해결된 대화, linear history를 요구합니다. 일반 CI에 real AWS credential은 필요하지 않습니다.

## Dependency update

Dependabot은 [공식 설정 방식](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates)으로 Python, GitHub Actions, Docker를 매주 확인합니다. boto3/botocore는 protocol과 client 직렬화를 함께 검토하도록 묶습니다.

AWS SDK 업데이트는 contract manifest, operation coverage, 한·영 문서, boto3 contract가 모두 일치해야 완료됩니다.

## ECR 게시

Repository variable `AWS_ROLE_ARN`, `AWS_REGION`, `ECR_REGISTRY`를 설정합니다. GitHub OIDC token으로 AWS role을 교환하며 장기 AWS key를 저장하지 않습니다. [AWS OIDC provider 지침](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)을 참고하세요.

Tag는 `vMAJOR.MINOR.PATCH`를 사용합니다. 각 component는 version과 `latest`를 게시하지만 production은 immutable version 또는 digest를 고정해야 합니다. Rollback은 이전 digest 재배포이며 기존 version tag를 덮어쓰지 않습니다.

## 실패 artifact

CI는 coverage, model drift, Docker log, test artifact를 항상 보존하려고 시도합니다. 로그는 component 경계와 side effect event를 담되 secret은 포함하지 않습니다.

