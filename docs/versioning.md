<!-- doc-id: versioning -->
<!-- lang: en -->

[한국어](versioning.ko.md) | [English](versioning.md)

# Versioning and branch delivery

This is the maintainer guide for the `feature/*` → `develop` → `main` workflow. `VERSION` is the
only committed version authority. It contains a stable [Semantic Versioning](https://semver.org/)
core such as `1.4.0`; contributors never commit a snapshot suffix.

<!-- section: commands -->
## Local command surface

```bash
make version-show
make version-check
make version-bump PART=patch
make version-bump PART=minor VERSION_ARGS=--dry-run
uv run python scripts/version.py set 1.4.0
uv run python scripts/version.py check --base-ref origin/main
```

`version-bump` and `set` update every file declared in `config/version-files.json`, print a unified
diff, and stop on a dirty working tree. `--dry-run` writes nothing. `--allow-dirty` is intended only
for controlled automation. These commands never commit, push, tag, publish an image, or create a
release. Python snapshot versions use the official [PEP 440 version
scheme](https://packaging.python.org/en/latest/specifications/version-specifiers/) while public OCI
tags retain the documented SemVer-derived form.

Equivalent local Git flow:

```bash
git switch develop
git pull --ff-only
git switch -c prepare/version-next
make version-bump PART=minor
make version-check BASE_REF=origin/main
git add --all
git commit -m "chore(release): prepare next version"
git push -u origin prepare/version-next
gh pr create --base develop
```

<!-- section: git-ui -->
## GitHub UI flow

Open **Actions**, select **Prepare version PR**, select **Run workflow**, and choose `patch`, `minor`,
`major`, or `exact`. For `exact`, enter a stable `X.Y.Z`; otherwise leave the exact-version field
blank. The workflow creates a `prepare/version-*` branch and opens a PR against `develop`. It has no
package permission and cannot publish. This follows GitHub's official [manual workflow
procedure](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/manually-running-a-workflow).
The repository's restricted default token remains read-only; only this job requests `contents` and
`pull-requests` write. GitHub's [workflow-permission
setting](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository?apiVersion=2022-11-28)
must allow Actions to create pull requests. The workflow never approves or merges its own PR.

<!-- section: branches -->
## Branch and event policy

| Event | Result | Side effect |
| --- | --- | --- |
| PR to `develop` or `main` | build, test, and version validation | none |
| `feature/*` push | build and test | none |
| successful CI for a `develop` push | `vX.Y.Z-snapshot.RUN.gSHA8` | all three GHCR images only |
| successful CI for a `main` push | `vX.Y.Z` | annotated tag, all images, GitHub Release |
| failed CI, PR-origin CI, manual CI, or another branch | denied | none |

The unprivileged CI workflow has `contents: read`. Publication starts only from GitHub's
[`workflow_run` completed event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)
and checks the source event, workflow name, branch, conclusion, and exact head SHA again. Reusable
workflow permissions follow GitHub's [permission
model](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions):
only the image job receives `packages: write`; only annotated-tag and release jobs receive
`contents: write`.

<!-- section: transaction -->
## Publication transaction

The exact accepted SHA is checked out in every job. Repository contracts and release-acceptance
cases run before local multi-platform builds and pinned Trivy scans. A content-hashed aggregate
authorization must cover every configured component/platform pair. A stable run then creates its
annotated tag using GitHub's documented two-step [tag object and tag reference
API](https://docs.github.com/en/rest/git/tags), publishes Proxy, EMR, and Glue, verifies both OCI
platforms and revision labels without a registry login, and finally creates a GitHub Release with
generated notes through the official [Releases API](https://docs.github.com/en/rest/releases/releases).

`latest` is not published. Snapshot and stable tags are immutable by policy. A retry may resume a
tag, image, or release only when its revision label/tag target equals the original SHA. A different
SHA fails before overwrite. The stable release is deliberately created last, so it never advertises
images that failed anonymous verification.

Snapshot retention is recorded as 30 days in `config/registry-release.json` and in each run's
`retention.json`. Deletion is not automated yet; stable images are not part of snapshot cleanup.

<!-- section: governance -->
## Repository rulesets

Configure both branches with GitHub [repository
rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets):

- `main`: pull requests only, linear history, no deletion or force push, and `Required CI` required.
- `develop`: pull requests preferred, linear history, no deletion or force push, and `Required CI`
  required.
- `feature/*`: no publication workflow trigger and no package-writing token.

Approval count is a repository-owner choice and is intentionally not embedded in code. Concurrency
serializes publication by branch; the version and immutable-binding checks remain the final defense
against stale PRs and retries.

`config/github-rulesets.json` is the reviewable authority. Approval count remains a configuration
choice and defaults to zero for this single-maintainer repository. Validate or converge only the two
Mystack-owned rulesets with:

```bash
make rulesets-check
make rulesets-apply REPOSITORY=leeyh0216/mystack DRY_RUN=--dry-run
make rulesets-apply REPOSITORY=leeyh0216/mystack
```

The apply command creates or updates rulesets by their exact managed names and never deletes or
modifies an unrelated ruleset. It requires repository administration permission and uses the
official [repository rulesets REST API](https://docs.github.com/en/rest/repos/rules).

<!-- section: recovery -->
## Failure and recovery map

| Failure/event | Meaning | Recovery |
| --- | --- | --- |
| `version.drift.check` | A derived file differs from `VERSION` | Run `make version-check`, then `version.py set` with the intended version |
| `release.policy.failed` | Event/ref/source workflow cannot publish | Use a normal PR; do not add write permission to CI |
| `github.tag.ensure.*` | Stable tag creation or same-SHA resume | Rerun the failed release for the same SHA |
| immutable binding conflict | Tag/image belongs to another SHA | Bump `VERSION`; never overwrite the tag |
| partial image set | Some component images exist on the same SHA | Rerun the same workflow run; matching images are verified and skipped |
| anonymous verification denied | GHCR package is not public | Complete the one-time visibility procedure in `container-release.md`, then rerun |
| `registry.index.verify.failed` | OCI platform set differs from config | Fix the Dockerfile/base index and publish a new version |
| release creation failed | Images passed but GitHub Release is absent | Rerun the same SHA; tag and images are safely resumed |

Every external command has a timeout. Boundary logs include action, branch, version, component,
revision, and a repair hint, but never tokens. Inspect the Actions run artifacts for preflight scans,
aggregate authorization, published indexes, and retention metadata.

<!-- section: support -->
## Supported and excluded policy

This automation publishes the three configured Linux `amd64`/`arm64` images to GHCR and creates
stable GitHub tags/releases. It does not publish Python/npm packages, `latest`, per-component manual
releases, registry mirrors, signed Git tags, automated snapshot deletion, or real AWS artifacts.
Adding any of those changes the release contract and requires a separate issue, configuration
schema change, tests, and bilingual documentation.
