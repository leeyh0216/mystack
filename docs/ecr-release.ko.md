# Private ECR 릴리스와 롤백

한국어 | [English](ecr-release.md)

이 runbook은 Proxy, EMR, Glue version image 게시를 담당합니다. Runtime 선택은
[`config/ecr-release.json`](../config/ecr-release.json), AWS resource는
[`infra/ecr/template.yaml`](../infra/ecr/template.yaml), orchestration은
[`docker-publish.yml`](../.github/workflows/docker-publish.yml)에 있습니다. Workflow는 공식
[Amazon ECR multi-architecture manifest list 계약](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-multi-architecture-image.html)과
[GitHub-AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)를
따르므로 장기 AWS access key를 GitHub에 저장하지 않습니다.

## 담당 릴리스 계약

| 관심사 | 계약 | 변경 지점 |
| --- | --- | --- |
| Component와 repository | `proxy`, `emr`, `glue` 항목 | `config/ecr-release.json` |
| Architecture | OCI index에 `linux/amd64`, `linux/arm64` 존재 | 같은 파일의 `platforms` |
| Supply-chain 증거 | BuildKit 최대 provenance와 SBOM attestation | `docker-publish.yml` |
| 취약점 정책 | 실제 platform digest를 각각 scan하고 설정 severity 차단 | 같은 파일의 `scan` |
| Tag 안전성 | ECR repository immutable, `latest` tag 없음 | CloudFormation과 workflow |
| Rollback | 알려진 multi-platform digest에 고유 tag를 추가한 뒤 재검증 | `scripts/ecr_release.py` |

Buildx는 `unknown/unknown` platform의 attestation descriptor를 추가할 수 있습니다. Verifier는
그 descriptor는 제외하고 설정된 runtime platform 둘을 반드시 요구합니다. 최상위 OCI index는
운영체제 image가 아니므로 각 하위 digest에서 ECR scan finding을 조회합니다. Amazon은 basic과
enhanced 동작을 [ECR image scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)에
정의합니다.

## AWS와 GitHub 최초 설정

IAM, ECR, CloudFormation resource를 만들 AWS CLI 권한과 repository 관리 권한이 필요합니다.
AWS region을 정한 뒤 GitHub가 이름 기반 claim과 불변 ID 기반 claim 중 무엇을 쓰는지 추측하지
말고 현재 OIDC subject prefix를 조회합니다.

```bash
gh api repos/leeyh0216/mystack/actions/oidc/customization/sub
```

응답의 `sub_claim_prefix`를 사용합니다. 이 repository는 현재
`repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID` 형태의 불변 prefix를 사용합니다. GitHub는
2026년 7월 15일 이후 생성 repository의 불변 subject와 정확한 claim 형태를
[OIDC reference](https://docs.github.com/en/actions/reference/security/oidc)에 설명합니다.

Account에 GitHub OIDC provider가 이미 있으면 ARN을 넘깁니다. 없으면 parameter를 비워 stack이
provider를 만들게 합니다.

```bash
aws cloudformation deploy \
  --stack-name mystack-ecr \
  --template-file infra/ecr/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-2 \
  --parameter-overrides \
    GitHubSubjectPrefix='repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID' \
    ExistingGitHubOidcProviderArn=''
```

`ecr-production` GitHub environment를 만들거나 유지합니다. Static access key 이름의
secret이 아니라 CloudFormation output을 environment variable로 등록합니다.

| Variable | 값 |
| --- | --- |
| `AWS_ROLE_ARN` | `GitHubReleaseRoleArn` output |
| `AWS_REGION` | 배포 region, 예: `ap-northeast-2` |
| `ECR_REGISTRY` | scheme을 제외한 `Registry` output |

Repository plan이 지원하면 environment에 required reviewer나 deployment branch 보호를
추가합니다. GitHub도 OIDC 배포에 environment 보호 규칙을 권장합니다. 일부 plan은 private
repository에 이 규칙을 제공하지 않으므로, 이 경우에도 trust policy는 `aud`를
`sts.amazonaws.com`, `sub`를 이 repository와 `ecr-production` environment로 제한해야 합니다.

## 게시

Release tag 경로는 모든 component를 build합니다. ECR tag immutability 때문에 같은 tag를 다시
게시하면 문서에 정의된 `ImageTagAlreadyExistsException`이 발생하므로 새 semantic version을
선택합니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

Pre-release는 GitHub Actions의 **Publish or roll back ECR images**에서 `publish`와 component를
선택합니다. `version`을 비우면 고유한 `manual-RUN_ID-ATTEMPT` tag가 생깁니다. 성공 job은 최상위
digest, media type, platform digest, severity count, 정책 결과를 artifact로 남깁니다. 배포에는
tag가 아닌 `REGISTRY/REPOSITORY@sha256:...`를 사용합니다.

Action과 base image는 pin되어 있습니다. Pin을 바꿀 때는 공식 changelog를 검토하고 두
architecture를 다시 build하며 API coverage/model drift gate를 통과해야 합니다. BuildKit
`provenance`, `sbom` 입력은 공식
[build-push-action 계약](https://github.com/docker/build-push-action)을 따릅니다.

## 이력을 변경하지 않는 rollback

성공한 release artifact 또는 ECR에서 과거 최상위 digest를 찾습니다. 같은 workflow를
`rollback`, 하나의 구체적인 component, 전체 `sha256:...` digest로 수동 실행합니다. Rollback
tag를 비우면 고유 값이 생성됩니다. Script는 `BatchGetImage`로 정확한 OCI index를 가져오고
`PutImage`로 새 tag를 연결한 뒤 manifest와 취약점 검사를 반복합니다. 이 pull/push 없는
manifest 동작은 [ECR retagging 안내](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-retag.html)에
문서화되어 있습니다.

Rollback은 현재 image를 삭제하거나 기존 version을 덮어쓰거나 `latest`를 게시하지 않습니다.
Consumer가 artifact의 검증된 digest를 사용하도록 변경되어야 배포 rollback이 완료됩니다.

## 실패 대응표

모든 side effect는 구조화된 `ecr.*.before`, `.after`, `.poll`, `.failed` JSON event를 남깁니다.
Report에는 credential이나 전체 manifest가 포함되지 않습니다.

| Event 또는 실패 | 의미 | 수정 위치 |
| --- | --- | --- |
| `Set AWS_ROLE_ARN...` | GitHub environment 미설정 | Environment variable과 CloudFormation output |
| OIDC `Not authorized to perform sts:AssumeRoleWithWebIdentity` | `aud`, subject prefix, environment 불일치 | Role trust policy parameter, GitHub OIDC endpoint 재조회 |
| `ecr.platform.verify.failed` | Build 결과에서 설정 architecture 누락 | Dockerfile/base manifest 또는 `platforms` 설정 |
| `ecr.scan.wait... timeout` | 명시한 시간 내 ECR/Inspector 미완료 | `scan.timeout_seconds`, ECR scan 설정, Inspector event |
| `ecr.scan.policy.failed` | 차단 severity finding 존재 | Base/runtime dependency 보완 후 새 tag build |
| `ImageTagAlreadyExistsException` | 새 tag가 이미 존재 | 새 version/manual/rollback tag 사용, immutability 유지 |
| digest mismatch | Build, 조회, 요청 identity 불일치 | 릴리스 중단 후 Buildx output과 ECR audit event 점검 |

Workflow와 script는 90/30분 job timeout과 파일로 설정한 scan timeout을 강제합니다. Timeout을
없애지 말고 `config/ecr-release.json`에서 명시적으로 조정합니다.

## AWS write 없는 local 검증

```bash
uv run pytest tests/test_ecr_release.py --timeout 60 --timeout-method thread -vv
uv run ruff check scripts/ecr_release.py tests/test_ecr_release.py
docker compose config --quiet
```

실제 게시는 의도적으로 GitHub environment와 AWS account가 있어야 합니다. 일반 CI와
local 개발에는 real-AWS credential이 필요하지 않습니다.
