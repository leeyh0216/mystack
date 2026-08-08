# Private GHCR image 게시

한국어 | [English](container-release.md)

Mystack은 Proxy, EMR, Glue를 private multi-platform OCI image로 GitHub Container Registry에
게시합니다. AWS/GCP account, cloud role, personal access token, repository secret이 필요하지
않습니다. GitHub 공식 [Container registry 문서](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)는
workflow repository와 연결된 package를 `GITHUB_TOKEN`으로 게시할 수 있고 최초 package는
기본적으로 private이라고 정의합니다.

## Image와 소유권

| Component | Package |
| --- | --- |
| Proxy | `ghcr.io/leeyh0216/mystack-proxy` |
| EMR | `ghcr.io/leeyh0216/mystack-emr` |
| Glue | `ghcr.io/leeyh0216/mystack-glue` |

Owner는 실행 시 `github.repository_owner`를 소문자로 변환해 결정하며 표는 현재 repository를
나타냅니다. Component package name, Dockerfile, platform, Trivy version, severity 정책, timeout은
[`config/registry-release.json`](../config/registry-release.json)에 있습니다. Workflow orchestration은
[`container-publish.yml`](../.github/workflows/container-publish.yml)에 있습니다.

게시 job에는 `contents: read`, `packages: write`만 부여합니다. GitHub 공식
[Docker image 게시 예제](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)에
따라 일회성 `GITHUB_TOKEN`으로 `ghcr.io`에 로그인합니다. Registry credential은 log나 secret으로
별도 저장하지 않습니다.

## 게시 계약

- `vMAJOR.MINOR.PATCH` tag는 세 component를 모두 게시합니다.
- 수동 실행은 한 component 또는 전체를 게시하며 version을 비우면 고유한
  `manual-RUN_ID-ATTEMPT` tag를 생성합니다.
- `latest`는 게시하지 않습니다. Production과 재현 가능한 개발 환경은 보고된 digest를
  사용합니다.
- 기존 tag는 build 전에 거부합니다. GHCR에는 repository 수준 immutable tag 기능이 없으므로
  모든 게시 job을 직렬화해 repository 내부 race를 방지합니다.
- Buildx는 하나의 OCI image index에 `linux/amd64`, `linux/arm64`를 게시합니다.
- BuildKit이 최대 provenance와 SBOM을 연결합니다. GitHub 문서상 private repository에서 GitHub
  artifact attestation은 Enterprise Cloud가 필요하므로 해당 서비스는 사용하지 않습니다.
- 게시한 index를 digest로 다시 받아 공식
  [OCI Image Index 명세](https://github.com/opencontainers/image-spec/blob/main/image-index.md)에 맞춰
  검증합니다.
- 고정된 Trivy version으로 두 platform manifest를 검사하고, 설정에 따라 unfixed finding을
  제외한 뒤 파일 정책 severity를 차단합니다. 공식 Trivy CLI가
  [`--platform` 계약](https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/)을
  정의합니다.
- 모든 job과 scan은 명시적 timeout을 사용합니다. Release, raw index, platform별 scan, 정책 요약
  증거는 이후 step이 실패해도 upload합니다.

BuildKit provenance/SBOM descriptor는 `unknown/unknown`일 수 있습니다. Validator는 이
attestation을 제외하고 설정된 runtime platform 둘을 반드시 요구합니다. Mystack은 OCI 출력을
검증할 뿐 OCI registry나 image format protocol을 구현하지 않습니다.

## 게시

Semantic release는 다음과 같습니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

한 component pre-release는 다음과 같습니다.

```bash
gh workflow run container-publish.yml \
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

## 취약점 결과와 rollback 의미

GHCR에는 ECR 같은 scan-on-push API가 없습니다. 따라서 Trivy는 Buildx가 index를 게시한 직후
검사합니다. 정책이 실패하면 workflow는 red지만 고유 tag image는 이미 존재합니다. 실패 tag를
덮어쓰지 말고 base/runtime을 보완해 새 version을 게시합니다. Artifact에는 두 platform report가
모두 남습니다.

Rollback에는 registry 변경이 필요하지 않습니다. Consumer를 이전에 검증된
`image@sha256:...` identity로 되돌립니다. Tag는 사람이 읽는 release label이고 digest가 배포
identity입니다.

## 실패 대응표

| Event 또는 실패 | 의미 | 변경 지점 |
| --- | --- | --- |
| `registry.tag.check.failed` | 요청 tag가 이미 존재 | 새 semantic/manual tag 선택 |
| package permission denied | Workflow/package 연결 또는 `packages: write` 불일치 | Package access와 workflow permission |
| `registry.index.verify.failed` | Architecture 누락 | Dockerfile base manifest 또는 `platforms` 설정 |
| Trivy timeout | Image/DB download가 제한 초과 | Release config의 `scan.timeout` |
| `registry.scan.evaluate.failed` | 설정된 fixed 취약점 존재 | Base/runtime pin 보완 후 새 version |
| digest mismatch/pull failure | 게시 identity 또는 token access 불일치 | Build output, package access, consumer digest |

Boundary event는 `registry.*.before`, `.after`, `.failed`를 사용하며 credential, image layer, 전체
environment 값은 기록하지 않습니다.

## Local 검사

```bash
make registry-check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/container-publish.yml
```

Local 검사는 push하지 않습니다. Version tag 또는 명시적 수동 workflow만 GHCR을 변경합니다.
