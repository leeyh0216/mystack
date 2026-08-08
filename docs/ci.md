# CI, dependency, and release automation

[한국어](ci.ko.md) | English

## Workflows

| Workflow | Trigger | Contract |
| --- | --- | --- |
| `ci.yml` | push, pull request, manual | Python 3.11/3.12, lint, formatting, docs, model/requirements drift, Compose, unit/architecture/contract tests, packages |
| `model-drift.yml` | weekly, manual | latest botocore versus pinned model; opens or updates one actionable issue |
| `e2e.yml` | relevant pull request, nightly, manual | Docker black-box boto3/Spark/Hive/Iceberg and required Chromium console accessibility E2E with logs retained |
| `docker-publish.yml` | version tag, manual | amd64/arm64 Proxy/EMR/Glue images, provenance, SBOM, private ECR push |

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

Configure repository variables `AWS_ROLE_ARN`, `AWS_REGION`, and `ECR_REGISTRY`. GitHub exchanges its OIDC token for the configured AWS role; do not store long-lived AWS keys. See [AWS OIDC provider guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html).

Tags use `vMAJOR.MINOR.PATCH`. Each component publishes the version and `latest`; production deployments should pin the immutable version or digest. Rollback means redeploying the prior digest, never rewriting an existing version tag.

## Failure artifacts

CI always attempts to preserve coverage, model drift, Docker logs, and test artifacts. Logs must retain component boundary and side-effect events but never secrets.
