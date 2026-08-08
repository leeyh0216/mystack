# Private ECR release and rollback

[한국어](ecr-release.ko.md) | English

This runbook owns versioned Proxy, EMR, and Glue image publication. Runtime choices live in
[`config/ecr-release.json`](../config/ecr-release.json); AWS resources live in
[`infra/ecr/template.yaml`](../infra/ecr/template.yaml); orchestration lives in
[`docker-publish.yml`](../.github/workflows/docker-publish.yml). The workflow follows the official
[Amazon ECR multi-architecture manifest-list contract](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-multi-architecture-image.html)
and uses [GitHub-to-AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws),
so no long-lived AWS access key belongs in GitHub.

## Owned release contract

| Concern | Contract | Change point |
| --- | --- | --- |
| Components and repositories | `proxy`, `emr`, and `glue` entries | `config/ecr-release.json` |
| Architectures | OCI index contains `linux/amd64` and `linux/arm64` | `platforms` in the same file |
| Supply-chain evidence | BuildKit maximum provenance and SBOM attestations | `docker-publish.yml` |
| Vulnerability policy | Scan every concrete platform digest; fail configured severities | `scan` in the same file |
| Tag safety | ECR repositories are immutable; there is no `latest` tag | CloudFormation and workflow |
| Rollback | Add a unique tag to one known multi-platform digest, then verify again | `scripts/ecr_release.py` |

Buildx may add attestation descriptors with `unknown/unknown` platforms. The verifier deliberately
ignores those descriptors and requires both configured runtime platforms. It then calls ECR scan
findings for each child digest, because the top-level OCI index is not an operating-system image.
Amazon documents basic and enhanced behavior in [ECR image scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html).

## One-time AWS and GitHub setup

Prerequisites are AWS CLI credentials authorized to create IAM, ECR, and CloudFormation resources,
plus repository administration permission. Choose an AWS region. Retrieve the repository's current
OIDC subject prefix instead of guessing whether GitHub uses name-based or immutable ID-based claims:

```bash
gh api repos/leeyh0216/mystack/actions/oidc/customization/sub
```

Use the returned `sub_claim_prefix`. For this repository it currently has the immutable form
`repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID`. GitHub documents that repositories created after
July 15, 2026 use immutable subjects and describes the exact claim shapes in its
[OIDC reference](https://docs.github.com/en/actions/reference/security/oidc).

If the account already has the GitHub OIDC provider, pass its ARN. Otherwise leave that parameter
empty and the stack creates the provider:

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

Create or retain the `ecr-production` GitHub environment. Add environment variables—not
secrets named as static access keys—from the CloudFormation outputs:

| Variable | Value |
| --- | --- |
| `AWS_ROLE_ARN` | `GitHubReleaseRoleArn` output |
| `AWS_REGION` | deployed region, for example `ap-northeast-2` |
| `ECR_REGISTRY` | `Registry` output without a scheme |

Where the repository plan supports them, add required reviewers or deployment-branch protection to
that environment. GitHub explicitly recommends environment protection rules for OIDC deployments.
Some plans do not offer those rules for private repositories; the trust policy must still limit
`aud` to `sts.amazonaws.com` and `sub` to this repository and `ecr-production` environment.

## Publish

The release tag path builds all components. ECR tag immutability means a repeated tag is rejected
with the documented `ImageTagAlreadyExistsException`, so select a new semantic version:

```bash
git tag v0.1.0
git push origin v0.1.0
```

For a pre-release, run **Publish or roll back ECR images** from GitHub Actions with `publish`, choose
one component or all, and leave `version` blank for a unique `manual-RUN_ID-ATTEMPT` tag. A successful
job records the top-level digest, media type, platform digests, severity counts, and policy result in
an artifact. Deploy using `REGISTRY/REPOSITORY@sha256:...`, not a tag.

Actions and base images are pinned. Updating a pin requires reviewing its official changelog,
rebuilding both architectures, and keeping the API coverage/model drift gates green. BuildKit's
`provenance` and `sbom` inputs follow the official
[build-push-action contract](https://github.com/docker/build-push-action).

## Roll back without mutating history

Find a previously successful top-level digest in a release artifact or ECR. Manually dispatch the
same workflow with `rollback`, one concrete component, and the full `sha256:...` digest. Leave the
rollback tag blank to generate a unique value. The script retrieves the exact OCI index with
`BatchGetImage`, associates a new tag through `PutImage`, and repeats manifest and vulnerability
checks. The [ECR retagging guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-retag.html)
documents this no-pull/no-push manifest operation.

Rollback does not delete the current image, rewrite an existing version, or publish `latest`.
Deployment rollback is complete only after the consumer is changed to the artifact's verified
digest.

## Failure map

Every side effect has structured `ecr.*.before`, `.after`, `.poll`, or `.failed` JSON events. Reports
never contain credentials or complete manifests.

| Event or failure | Meaning | Fix location |
| --- | --- | --- |
| `Set AWS_ROLE_ARN...` | GitHub environment is not bootstrapped | Environment variables and CloudFormation outputs |
| OIDC `Not authorized to perform sts:AssumeRoleWithWebIdentity` | `aud`, subject prefix, or environment differs | Role trust policy parameters; re-read GitHub OIDC endpoint |
| `ecr.platform.verify.failed` | Build output lost a configured architecture | Dockerfile/base manifest or `platforms` config |
| `ecr.scan.wait... timeout` | ECR/Inspector did not finish within the explicit limit | `scan.timeout_seconds`, ECR scanning configuration, Inspector events |
| `ecr.scan.policy.failed` | A configured severity has findings | Patch base/runtime dependencies, rebuild with a new tag |
| `ImageTagAlreadyExistsException` | A supposedly new tag already exists | Use a new version/manual/rollback tag; never relax immutability |
| digest mismatch | Built, fetched, and requested identities disagree | Stop the release; inspect Buildx output and ECR audit events |

The workflow and script enforce explicit 90/30-minute job limits and a file-configured scan timeout.
Do not solve a timeout by removing it; make the bound explicit in `config/ecr-release.json`.

## Local verification without AWS writes

```bash
uv run pytest tests/test_ecr_release.py --timeout 60 --timeout-method thread -vv
uv run ruff check scripts/ecr_release.py tests/test_ecr_release.py
docker compose config --quiet
```

An actual publish intentionally requires the GitHub environment and an AWS account. Normal
CI and local development do not need real-AWS credentials.
