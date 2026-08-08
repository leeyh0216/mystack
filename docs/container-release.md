<!-- doc-id: container-release -->
<!-- lang: en -->

[한국어](container-release.ko.md) | [English](container-release.md)

# Private GHCR image publication

Mystack publishes Proxy, EMR, and Glue as private multi-platform OCI images in GitHub Container
Registry. Publication needs no AWS/GCP account, cloud role, personal access token, or repository
secret. GitHub's official [Container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
supports `GITHUB_TOKEN` for a package associated with its workflow repository and makes a newly
published package private by default.

<!-- section: images -->
## Images and ownership

| Component | Package |
| --- | --- |
| Proxy | `ghcr.io/leeyh0216/mystack-proxy` |
| EMR | `ghcr.io/leeyh0216/mystack-emr` |
| Glue | `ghcr.io/leeyh0216/mystack-glue` |

The owner is resolved from `github.repository_owner` and lowercased at runtime; the table shows the
current repository. Component package names, Dockerfiles, platforms, Trivy version, severity policy,
and timeouts live in [`config/registry-release.json`](../config/registry-release.json). Event-facing
orchestration lives in [`release.yml`](../.github/workflows/release.yml); the called
[`container-publish.yml`](../.github/workflows/container-publish.yml) accepts only `workflow_call`.

GitHub does not let a called workflow elevate the caller token, so the caller supplies a
`packages: write` ceiling. Every called job explicitly downgrades to `contents: read` except the
final `publish` job. Only that final job logs in to `ghcr.io` with the ephemeral `GITHUB_TOKEN`,
following GitHub's official
[Docker image publishing example](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
No registry credential is logged or stored.

<!-- section: contract -->
## Publication contract

- A `vMAJOR.MINOR.PATCH` tag publishes all three components.
- A manual dispatch can publish one component or all. Blank version input generates a unique
  `manual-RUN_ID-ATTEMPT` tag.
- `latest` is never published. Production and repeatable development should pull the reported digest.
- Validation runs repository checks plus every generated required compatibility contract/E2E case.
- Buildx then builds each configured component/platform into the local Docker engine with
  `push: false`. Pinned Trivy scans each local image and produces a content-hashed record.
- The aggregate job rejects missing, extra, modified, wrong-commit, wrong-version, or failed records.
  A failed, cancelled, or skipped prerequisite prevents the aggregate authorization and final job.
- Existing tags are rejected after authorization and before the registry-mutating build. GHCR does
  not provide repository-level immutable tags, so the entrypoint serializes releases to avoid races.
- Only after authorization does Buildx publish `linux/amd64` and `linux/arm64` in one OCI image
  index. The final image is rebuilt from the same commit, digest-pinned bases, and hash-locked
  dependencies because Docker's local exporter cannot directly publish a multi-platform index.
- BuildKit attaches maximum provenance and an SBOM. GitHub's own artifact-attestation service is not
  used because GitHub documents that private repositories need Enterprise Cloud for that feature.
- The published index is fetched by digest and validated against the official
  [OCI Image Index specification](https://github.com/opencontainers/image-spec/blob/main/image-index.md).
- Pinned Trivy scans both locally built platform images, ignores unfixed findings as configured, and
  rejects the severities in the file policy. Trivy's official
  [image command](https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/)
  searches the local Docker engine before a registry.
- Every job and scan has an explicit timeout. Raw local scans, content-hashed preflight records,
  aggregate authorization, published index, and release evidence are retained as artifacts.

BuildKit provenance/SBOM descriptors may use `unknown/unknown`; the validator ignores those
attestations while requiring both configured runtime platforms. Mystack validates the OCI output but
does not implement the OCI registry or image format protocol.

<!-- section: publish -->
## Publish

For a semantic release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

For an isolated pre-release:

```bash
gh workflow run release.yml \
  --repo leeyh0216/mystack \
  --ref main \
  -f component=proxy \
  -f version=
```

The first successful workflow creates private packages and links them to this repository. Package
visibility and repository access can later be changed in GitHub package settings. A consumer of a
private package needs `read:packages`, or a repository `GITHUB_TOKEN` to which package read access was
granted.

Pull a fixed image identity from the `release.json` artifact:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
docker pull ghcr.io/leeyh0216/mystack-proxy@sha256:FULL_INDEX_DIGEST
```

Use a classic PAT with only `read:packages` for local private pulls. Do not use an account password.

<!-- section: vulnerability -->
## Vulnerability result and rollback semantics

GHCR has no ECR-style scan-on-push API. Mystack therefore scans local images before authentication or
registry mutation. A validation, build, timeout, missing evidence, or vulnerability-policy failure
creates no final GHCR tag. Raw reports remain in `preflight-*` artifacts for diagnosis. Patch the
base/runtime and rerun with a new version; never weaken or overwrite evidence for a failed run.

Rollback does not require a registry mutation: change the consumer back to an earlier verified
`image@sha256:...` identity. Tags are human release labels; digests are deployment identities.

<!-- section: failures -->
## Failure map

| Event or failure | Meaning | Change point |
| --- | --- | --- |
| `registry.preflight.record.*` | One local component/platform build was scanned | Dockerfile, platform, or scan policy |
| `registry.gate.verify.*` | Complete content-hashed evidence set was checked | Missing/extra artifact, source SHA, version, or scan result |
| `registry.publication.authorize.*` | Final job rebound the authorization to its context | Rerun the complete release; never copy a gate between runs |
| `registry.tag.check.failed` | The requested tag already exists | Choose a new semantic/manual tag |
| package permission denied | Workflow/package link or `packages: write` differs | Package access and workflow permissions |
| `registry.index.verify.failed` | An architecture disappeared | Dockerfile base manifest or `platforms` config |
| Trivy timeout | Image/DB download exceeded the bound | `scan.timeout` in release config |
| `registry.scan.evaluate.failed` | Configured fixed vulnerability exists | Base/runtime pins, then a new version |
| digest mismatch/pull failure | Published identity or token access differs | Build output, package access, consumer digest |

Boundary events use `registry.*.before`, `.after`, and `.failed`; credentials, image layers, and full
environment values are never logged.

<!-- section: local-checks -->
## Local checks

```bash
make registry-check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/release.yml .github/workflows/container-publish.yml
```

Local checks do not push. Only a version tag or an explicit manual workflow dispatch can mutate GHCR.
