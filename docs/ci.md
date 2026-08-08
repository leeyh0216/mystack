# CI, dependency, and release automation

[한국어](ci.ko.md) | English

## Workflows

| Workflow | Trigger | Contract |
| --- | --- | --- |
| `ci.yml` | push, pull request, manual | Python 3.11/3.12, lint, formatting, docs, model/requirements drift, Compose, unit/architecture/contract tests, packages |
| `model-drift.yml` | weekly, manual | latest botocore versus pinned model; opens or updates one actionable issue |
| `e2e.yml` | relevant pull request, nightly, manual | Docker black-box boto3/Spark/Hive/Iceberg and required Chromium console accessibility E2E with logs retained |
| `docker-publish.yml` | version tag, manual | immutable amd64/arm64 Proxy/EMR/Glue publish, scan evidence, and rollback retag |

Workflow design follows [GitHub Actions workflow documentation](https://docs.github.com/actions/writing-workflows). Timeouts are explicit in CI and sourced from YAML locally.

## Branch protection expectations

Require the Python contract matrix and Docker E2E for changes to runtime paths. Require reviewed pull requests, resolved conversations, and linear history. Direct real-AWS credentials are never required for normal CI.

## Dependency updates

Dependabot checks Python, GitHub Actions, and Docker weekly using the [official configuration mechanism](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates). boto3/botocore updates are grouped because protocol and client serialization must be reviewed together.

An AWS SDK update is incomplete until the contract manifest, operation coverage, Korean/English docs, and boto3 contracts agree.

Container dependencies are exported with hashes from `uv.lock`. `make requirements` updates the
three component files, and CI rejects stale exports using the official
[uv export mechanism](https://docs.astral.sh/uv/reference/cli/#uv-export). Default image bases are
immutable multi-architecture digests rather than mutable tags.

## ECR publication

Follow the complete [private ECR release and rollback runbook](ecr-release.md). Its CloudFormation
stack provisions immutable, scan-on-push repositories and a repository/environment-restricted OIDC
role. Configure `AWS_ROLE_ARN`, `AWS_REGION`, and `ECR_REGISTRY` as `ecr-production` environment
variables. GitHub exchanges its OIDC token for the role; never store long-lived AWS keys. See the
[official AWS OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

Version and rollback tags are append-only and `latest` is intentionally absent. Production consumers
pin the verified OCI index digest. Rollback associates a new unique tag with a prior digest and then
re-runs platform and scan verification.

## Failure artifacts

CI always attempts to preserve coverage, model drift, Docker logs, and test artifacts. Logs must retain component boundary and side-effect events but never secrets.
