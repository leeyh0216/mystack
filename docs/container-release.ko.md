<!-- doc-id: container-release -->
<!-- lang: ko -->

[한국어](container-release.ko.md) | [English](container-release.md)

# 비공개 GHCR 이미지 게시

Mystack은 Proxy, EMR, Glue를 private multi-platform OCI image로 GitHub Container Registry에
게시합니다. AWS/GCP account, cloud role, personal access token, repository secret이 필요하지
않습니다. GitHub 공식 [Container registry 문서](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)는
workflow repository와 연결된 package를 `GITHUB_TOKEN`으로 게시할 수 있고 최초 package는
기본적으로 private이라고 정의합니다.

<!-- section: images -->
## Image와 소유권

| Component | Package |
| --- | --- |
| Proxy | `ghcr.io/leeyh0216/mystack-proxy` |
| EMR | `ghcr.io/leeyh0216/mystack-emr` |
| Glue | `ghcr.io/leeyh0216/mystack-glue` |

Owner는 실행 시 `github.repository_owner`를 소문자로 변환해 결정하며 표는 현재 repository를
나타냅니다. Component package name, Dockerfile, platform, Trivy version, severity 정책, timeout은
[`config/registry-release.json`](../config/registry-release.json)에 있습니다. Event를 받는 orchestration은
[`release.yml`](../.github/workflows/release.yml)에 있고, 호출되는
[`container-publish.yml`](../.github/workflows/container-publish.yml)은 `workflow_call`만 받습니다.

GitHub는 호출된 workflow가 caller token 권한을 높이지 못하게 하므로 caller가
`packages: write` 상한을 제공합니다. 호출된 모든 job은 최종 `publish`를 제외하고 명시적으로
`contents: read`로 낮춥니다. 최종 job만 GitHub 공식
[Docker image 게시 예제](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)에
따라 일회성 `GITHUB_TOKEN`으로 `ghcr.io`에 로그인합니다. Registry credential은 log나 secret으로
별도 저장하지 않습니다.

<!-- section: contract -->
## 게시 계약

- `vMAJOR.MINOR.PATCH` tag는 세 component를 모두 게시합니다.
- 수동 실행은 한 component 또는 전체를 게시하며 version을 비우면 고유한
  `manual-RUN_ID-ATTEMPT` tag를 생성합니다.
- `latest`는 게시하지 않습니다. Production과 재현 가능한 개발 환경은 보고된 digest를
  사용합니다.
- Repository 검사와 생성된 모든 required compatibility contract/E2E case를 실행합니다.
- 그 다음 Buildx가 component/platform별 image를 local Docker engine에 `push: false`로 build합니다.
  고정 Trivy가 각 local image를 검사하고 content hash가 있는 record를 만듭니다.
- Aggregate job은 누락·추가·변조·잘못된 commit/version·실패 record를 거부합니다. 필수 job이
  실패·취소·skip되면 aggregate authorization과 최종 job에 도달하지 않습니다.
- 기존 tag는 authorization 뒤 registry를 변경하는 build 전에 거부합니다. GHCR에는 repository
  수준 immutable tag 기능이 없으므로 entrypoint가 release를 직렬화해 race를 방지합니다.
- Authorization 뒤에만 Buildx가 `linux/amd64`, `linux/arm64`를 한 OCI image index로 게시합니다.
  Docker local exporter가 multi-platform index를 직접 게시할 수 없으므로 같은 commit,
  digest-pinned base, hash-locked dependency에서 최종 image를 다시 build합니다.
- BuildKit이 최대 provenance와 SBOM을 연결합니다. GitHub 문서상 private repository에서 GitHub
  artifact attestation은 Enterprise Cloud가 필요하므로 해당 서비스는 사용하지 않습니다.
- 게시한 index를 digest로 다시 받아 공식
  [OCI Image Index 명세](https://github.com/opencontainers/image-spec/blob/main/image-index.md)에 맞춰
  검증합니다.
- 고정 Trivy version으로 local build한 두 platform image를 검사하고, 설정에 따라 unfixed finding을
  제외한 뒤 파일 정책 severity를 차단합니다. 공식 Trivy
  [image 명령](https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/)은 registry보다
  local Docker engine을 먼저 찾습니다.
- 모든 job과 scan은 명시적 timeout을 사용합니다. Local raw scan, content-hashed preflight record,
  aggregate authorization, 게시 index와 release 증거를 artifact로 보존합니다.

BuildKit provenance/SBOM descriptor는 `unknown/unknown`일 수 있습니다. Validator는 이
attestation을 제외하고 설정된 runtime platform 둘을 반드시 요구합니다. Mystack은 OCI 출력을
검증할 뿐 OCI registry나 image format protocol을 구현하지 않습니다.

<!-- section: publish -->
## 게시

Semantic release는 다음과 같습니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

한 component pre-release는 다음과 같습니다.

```bash
gh workflow run release.yml \
  --repo leeyh0216/mystack \
  --ref main \
  -f component=proxy \
  -f version=
```

최초 성공 workflow가 private package를 만들고 이 repository에 연결합니다. 이후 GitHub package
설정에서 visibility와 repository access를 바꿀 수 있습니다. Private package consumer에는
`read:packages` 또는 package read access를 부여한 repository `GITHUB_TOKEN`이 필요합니다.

`release.json` artifact의 고정 identity를 pull합니다.

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
docker pull ghcr.io/leeyh0216/mystack-proxy@sha256:FULL_INDEX_DIGEST
```

Local private pull에는 `read:packages`만 가진 classic PAT를 사용하고 account password는 사용하지
않습니다.

<!-- section: vulnerability -->
## 취약점 결과와 rollback 의미

GHCR에는 ECR 같은 scan-on-push API가 없습니다. Mystack은 인증이나 registry 변경 전에 local
image를 검사합니다. 검증, build, timeout, 근거 누락, 취약점 정책 중 하나라도 실패하면 최종 GHCR
tag를 만들지 않습니다. 진단용 raw report는 `preflight-*` artifact에 남습니다. Base/runtime을
보완하고 새 version으로 다시 실행하며 실패 실행의 근거를 약화하거나 덮어쓰지 않습니다.

Rollback에는 registry 변경이 필요하지 않습니다. Consumer를 이전에 검증된
`image@sha256:...` identity로 되돌립니다. Tag는 사람이 읽는 release label이고 digest가 배포
identity입니다.

<!-- section: failures -->
## 실패 대응표

| Event 또는 실패 | 의미 | 변경 지점 |
| --- | --- | --- |
| `registry.preflight.record.*` | Local component/platform build 검사 완료 | Dockerfile, platform 또는 scan 정책 |
| `registry.gate.verify.*` | Content hash가 있는 전체 근거 set 검증 | 누락/추가 artifact, source SHA, version 또는 scan 결과 |
| `registry.publication.authorize.*` | 최종 job context와 authorization 재결합 | 판정 근거를 복사하지 말고 전체 release 재실행 |
| `registry.tag.check.failed` | 요청 tag가 이미 존재 | 새 semantic/manual tag 선택 |
| package permission denied | Workflow/package 연결 또는 `packages: write` 불일치 | Package access와 workflow permission |
| `registry.index.verify.failed` | Architecture 누락 | Dockerfile base manifest 또는 `platforms` 설정 |
| Trivy timeout | Image/DB download가 제한 초과 | Release config의 `scan.timeout` |
| `registry.scan.evaluate.failed` | 설정된 fixed 취약점 존재 | Base/runtime pin 보완 후 새 version |
| digest mismatch/pull failure | 게시 identity 또는 token access 불일치 | Build output, package access, consumer digest |

Boundary event는 `registry.*.before`, `.after`, `.failed`를 사용하며 credential, image layer, 전체
environment 값은 기록하지 않습니다.

<!-- section: local-checks -->
## Local 검사

```bash
make registry-check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/release.yml .github/workflows/container-publish.yml
```

Local 검사는 push하지 않습니다. Version tag 또는 명시적 수동 workflow만 GHCR을 변경합니다.
