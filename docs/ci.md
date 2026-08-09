<!-- doc-id: ci -->
<!-- lang: en -->

[한국어](ci.ko.md) | [English](ci.md)

# CI, dependency, and release automation

<!-- section: workflows -->
## Workflows

| Workflow | Trigger | Contract |
| --- | --- | --- |
| `ci.yml` | `main`/`develop`/`feature/*` push, pull request, manual | Version readiness plus Python 3.11/3.12 contracts, required-case matrix, source-free GHCR Compose validation, and a frozen Dev Container build; `Required CI` aggregates the result |
| `model-drift.yml` | weekly, manual | latest botocore versus pinned model; opens or updates one actionable issue |
| `e2e.yml` | relevant pull request, nightly, manual | One isolated Docker job per explicit required boto3/AWS SDK for pandas/Spark/Hive/Iceberg case, plus Chromium console accessibility E2E |
| `release.yml` → reusable `container-publish.yml` | successful `CI` `workflow_run` for a direct `develop`/`main` push | Snapshot or stable policy resolution, required validation, local scans, immutable same-SHA publication, anonymous verification, and stable GitHub Release |
| `prepare-version-pr.yml` | manual | Version-file update branch and PR to `develop`; no package, tag, or release mutation |

Workflow design follows [GitHub Actions workflow documentation](https://docs.github.com/actions/writing-workflows). Timeouts are explicit in CI and sourced from YAML locally.
Actions reads only the `include` entries compiled into
`contracts/compatibility-matrix.generated.json`; it never constructs an implicit client/runtime
cross-product. The approach follows GitHub's [shared matrix
pattern](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations).
Pull requests and pushes select `required`; manual runs add `preview`, and scheduled/manual E2E runs
add `nightly`. An empty optional lane is valid because the event selection always merges it with the
non-empty required lane.
The Dev Container job uses the [official CLI](https://github.com/devcontainers/cli) with
`--frozen-lockfile` to reject feature digest drift and build the image to completion.

<!-- section: branch-protection -->
## Branch protection expectations

Use the repository rules in the [versioning guide](versioning.md). `main` is PR-only and `develop`
is PR-preferred; both reject force pushes/deletion, require linear history, and require `Required CI`.
The version-readiness job rejects a `main` PR without a new stable, unreleased version and repeats the
check on the accepted SHA. CI never calls a real AWS account and requires no cloud credentials.

<!-- section: dependencies -->
## Dependency updates

Dependabot checks Python, GitHub Actions, and Docker weekly using the [official configuration mechanism](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-dependabot-version-updates). boto3/botocore updates are grouped because protocol and client serialization must be reviewed together.

An AWS SDK update is incomplete until the contract manifest, operation coverage, exact immutable
artifact, generated Korean/English evidence, and boto3 contracts agree.

Container dependencies are exported with hashes from `uv.lock`. `make requirements` updates the
three component files, and CI rejects stale exports using the official
[uv export mechanism](https://docs.astral.sh/uv/reference/cli/#uv-export). Default image bases are
immutable multi-architecture digests rather than mutable tags.

<!-- section: publication -->
## GHCR publication

Follow the [version/branch workflow](versioning.md) and complete [public GHCR image
procedure](container-release.md). The publication job uses the
repository's ephemeral `GITHUB_TOKEN` with `packages: write`; there are no AWS/GCP credentials or
registry secrets. GitHub documents this authentication and automatic repository/package association
in the official [Container registry guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

The workflow creates a new package as private; an administrator then makes it public once by the
official visibility procedure. Consumers pull the resulting public images anonymously. Publication
authorization and consumption visibility are separate controls.

Stable and snapshot tags are append-only by workflow policy and `latest` is intentionally absent.
A retry resumes only artifacts carrying the same source SHA. Consumers pin the verified OCI index
digest; rollback selects a prior verified digest and does not mutate registry history.

<!-- section: artifacts -->
## Failure artifacts

CI always attempts to preserve coverage, model drift, Docker logs, and test artifacts. The release
validation artifact also retains the generated [release acceptance](compatibility/release-acceptance.generated.md),
compiled matrix, API classification, and deterministic Glue error catalog. Logs must retain
component boundary and side-effect events but never secrets.
