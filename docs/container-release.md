<!-- doc-id: container-release -->
<!-- lang: en -->

[한국어](container-release.ko.md) | [English](container-release.md)

# Public GHCR image publication

<!-- toc:start -->
## Contents

- [Images and ownership](#images-and-ownership)
- [Publication contract](#publication-contract)
- [Publishing and first-time visibility](#publishing-and-first-time-visibility)
- [Vulnerability and rollback semantics](#vulnerability-and-rollback-semantics)
- [Failure map](#failure-map)
- [Local non-publishing checks](#local-non-publishing-checks)
<!-- toc:end -->

This page covers container consumption and registry operations. Maintainers should read the full
[version and branch workflow](versioning.md) first. Mystack uses GitHub's official [Container
registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
and the repository-scoped `GITHUB_TOKEN`; no AWS/GCP account, cloud role, PAT, or custom registry
secret is required.

<!-- section: images -->
## Images and ownership

| Component | Public package |
| --- | --- |
| Proxy | `ghcr.io/leeyh0216/mystack-proxy` |
| EMR | `ghcr.io/leeyh0216/mystack-emr` |
| Glue | `ghcr.io/leeyh0216/mystack-glue` |

The owner is derived from and lowercased from `github.repository_owner`; the table shows this
repository. `config/registry-release.json` owns component names, Dockerfiles, platforms, scan policy,
timeouts, exact tag patterns, and snapshot retention. `latest` is not published.

<!-- section: contract -->
## Publication contract

- PR and feature events build/test only and have no package permission.
- Successful `develop` CI publishes all three images under one immutable snapshot tag.
- Successful `main` CI publishes all three images under the exact stable `vX.Y.Z`, creates an
  annotated tag for the same SHA, verifies anonymous access, then creates the GitHub Release.
- Each configured component/platform is built locally and scanned before login. Content-hashed
  evidence must authorize the entire set before registry mutation.
- A same-tag/same-SHA retry verifies and skips an existing component. A different SHA is rejected.
- BuildKit provenance and SBOM are attached. Runtime descriptors must satisfy the official [OCI
  image index](https://github.com/opencontainers/image-spec/blob/main/image-index.md); attestation
  descriptors with `unknown/unknown` are ignored.
- Pinned Trivy follows its official [image command
  contract](https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/). Every job,
  scan, test, and external command has an explicit timeout.

Mystack validates OCI output but does not implement a registry or OCI protocol.

<!-- section: publish -->
## Publishing and first-time visibility

Do not create or push release tags manually. Merge a reviewed, version-bumped PR through `develop`
to `main`; the successful `CI` run starts the post-CI transaction. For a version-only change, use
the **Prepare version PR** workflow or the commands in `versioning.md`.

A newly created personal-account package may initially be private. For each package once:

1. Open the account **Packages** page, choose the package, and open **Package settings**.
2. Under **Danger Zone**, choose **Change visibility**, select **Public**, and confirm the name.
3. Repeat for all three and rerun the same failed release SHA.

GitHub's official [personal-account visibility
procedure](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility#configuring-visibility-of-packages-for-your-personal-account)
warns that this public transition cannot be reversed. Automation deliberately does not perform it.
The workflow's anonymous verification fails until all three packages are public.

Consumers then pull without credentials, preferably using the verified digest:

```bash
docker pull ghcr.io/leeyh0216/mystack-proxy@sha256:FULL_INDEX_DIGEST
```

GitHub's [package permissions
guide](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages)
documents anonymous access for public container packages. Do not add a consumer token to hide a
visibility failure.

<!-- section: vulnerability -->
## Vulnerability and rollback semantics

GHCR has no ECR-style scan-on-push contract used by this project. Mystack scans local platform
images before authentication. A validation, build, timeout, missing-evidence, or configured
vulnerability failure prevents authorization. Raw `preflight-*` artifacts remain for diagnosis.

The scan gate rejects every configured severity by default. A known upstream runtime finding may
be accepted only through the exact entries in `config/registry-release.json`: component, CVE,
package, installed version, and image-relative JAR path must all match, and the review date must not
be past `expires_on`. The preflight evidence keeps raw counts, active counts, the bounded exception,
reason, expiry, and sources; an expired or slightly different finding becomes active and blocks the
release. This is the same risk-decision concept as Trivy's official [finding suppression
model](https://trivy.dev/docs/latest/guide/configuration/filtering/), but Mystack evaluates the
file-driven coordinates itself so the authorization artifact remains explicit and deterministic.

The current exceptions cover dependencies bundled by the fixed Spark 3.5.4/EMR 7.8 and AWS Glue 5
profiles. The Glue image removes job-only Maven cache, Delta, Hudi, Flink, streaming, Redshift, and
duplicate PySpark JAR surfaces before scanning. Derby LDAP authentication and ZooKeeper quorum
services are not started by either local emulator. The Avro and Parquet decisions do not claim that
the affected libraries are safe: Mystack has no authentication or multi-tenant boundary, an EMR
Step submitter already runs arbitrary operator-owned code, and Glue inputs must be trusted local
datasets until a verifiably fixed compatible runtime is pinned. The [Avro
advisory](https://nvd.nist.gov/vuln/detail/CVE-2024-47561), [Parquet
advisory](https://nvd.nist.gov/vuln/detail/CVE-2025-30065), [Derby
advisory](https://nvd.nist.gov/vuln/detail/CVE-2022-46337), and [ZooKeeper security
page](https://zookeeper.apache.org/security/) are attached to the policy. Maintainers must patch the
runtime or explicitly review a new expiry; never broaden a coordinate to make a scan green.

Rollback changes the consumer to an earlier verified `image@sha256:...`; it never overwrites a tag.
Snapshot metadata records a 30-day retention target, but deletion is not yet automated.

<!-- section: failures -->
## Failure map

| Event or failure | Meaning | Change point |
| --- | --- | --- |
| `registry.preflight.record.*` | One local component/platform passed scanning | Dockerfile, platform, or scan policy |
| `registry.gate.verify.*` | Complete evidence set was checked | Missing/extra artifact, source SHA, version, or scan result |
| immutable binding conflict | Existing image revision differs | Bump version; never overwrite |
| package permission denied during push | Workflow/package association differs | Workflow permission and package access |
| anonymous verification denied | Package is still private | Complete the one-time visibility change and rerun the same SHA |
| `registry.index.verify.failed` | Runtime platform is missing | Dockerfile base manifest or configured platforms |
| `registry.scan.exception.matched` | Exact reviewed finding is time-bounded | Review coordinate, rationale, sources, and expiry |
| `registry.scan.exception.expired` | A risk decision reached its deadline | Patch runtime or renew through review and a new version |
| `registry.scan.evaluate.failed` | Unapproved configured-severity finding exists | Patch runtime/base and use a new version |
| GitHub Release absent after images | Final transaction step failed | Rerun the same SHA; matching tag/images resume |

Logs use structured `.before`, `.after`, and `.failed` events around side effects. Tokens, complete
environment values, and image layers are never logged.

<!-- section: local-checks -->
## Local non-publishing checks

```bash
make version-check
make registry-check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/ci.yml \
  .github/workflows/release.yml \
  .github/workflows/container-publish.yml \
  .github/workflows/prepare-version-pr.yml
```

These checks do not push. Only successful post-CI `develop` or `main` publication receives a
package-writing token.
