<!-- doc-id: container-release -->
<!-- lang: ko -->

[한국어](container-release.ko.md) | [English](container-release.md)

# Public GHCR 이미지 게시

<!-- toc:start -->
## 목차

- [Image와 소유권](#image와-소유권)
- [게시 계약](#게시-계약)
- [게시와 최초 visibility 설정](#게시와-최초-visibility-설정)
- [취약점과 rollback 의미](#취약점과-rollback-의미)
- [실패 대응표](#실패-대응표)
- [게시하지 않는 local 검사](#게시하지-않는-local-검사)
<!-- toc:end -->

이 문서는 container 소비와 registry 운영을 설명합니다. Maintainer는 먼저 전체 [버전과 branch
흐름](versioning.ko.md)을 읽어야 합니다. Mystack은 GitHub 공식 [Container
registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)와
repository 범위 `GITHUB_TOKEN`을 사용합니다. AWS/GCP account, cloud role, PAT, 별도 registry secret은
필요하지 않습니다.

<!-- section: images -->
## Image와 소유권

| Component | Public package |
| --- | --- |
| Proxy | `ghcr.io/leeyh0216/mystack-proxy` |
| EMR | `ghcr.io/leeyh0216/mystack-emr` |
| Glue | `ghcr.io/leeyh0216/mystack-glue` |

Owner는 `github.repository_owner`를 소문자로 바꿔 결정하며 표는 이 repository를 나타냅니다.
`config/release/registry-release.json`이 component name, Dockerfile, platform, scan 정책, timeout, 정확한 tag
pattern, snapshot 보존 기간을 관리합니다. `latest`는 게시하지 않습니다.

<!-- section: contract -->
## 게시 계약

- PR과 feature event는 build/test만 수행하며 package permission이 없습니다.
- `develop` CI가 성공하면 세 image를 하나의 변경 불가 snapshot tag로 게시합니다.
- `main` CI가 성공하면 세 image를 정확한 `vX.Y.Z`로 게시하고 같은 SHA의 annotated tag를 만들며,
  익명 접근을 검증한 다음 GitHub Release를 만듭니다.
- Registry login 전에 설정된 component/platform별 local build와 scan을 수행합니다. Content hash가
  있는 전체 근거가 있어야 registry를 변경할 수 있습니다.
- 같은 tag와 같은 SHA의 재실행은 기존 component를 검증하고 건너뜁니다. SHA가 다르면 거부합니다.
- BuildKit provenance와 SBOM을 연결합니다. Runtime descriptor는 공식 [OCI image
  index](https://github.com/opencontainers/image-spec/blob/main/image-index.md)를 만족해야 하며
  `unknown/unknown`인 attestation descriptor는 제외합니다.
- Release를 마무리하기 전에 익명 runner가 게시한 Glue platform manifest digest를 각각 찾고 정확한
  `image@platform-digest`에 상한이 있는 `--verify-sqlite-runtime` command를 실행합니다. 이 report는
  앞선 local build 결과만 믿지 않고 artifact에서 source-built SQLite version, 검증한 WAL 경로,
  runtime architecture를 보여줍니다.
- 고정 Trivy는 공식 [image 명령
  계약](https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/)을 따릅니다. 모든
  job, scan, test, 외부 명령에는 명시적 timeout이 있습니다.

Mystack은 OCI 출력을 검증하지만 registry나 OCI protocol을 구현하지 않습니다.

<!-- section: publish -->
## 게시와 최초 visibility 설정

Release tag를 직접 만들거나 push하지 않습니다. 검토와 version 증가를 마친 PR을 `develop`에서
`main`으로 전달하면 성공한 `CI`가 후속 transaction을 시작합니다. Version만 바꾸려면 **Prepare
version PR** workflow 또는 `versioning.ko.md`의 명령을 사용합니다.

Personal account에서 처음 만든 package는 private일 수 있습니다. 각 package에서 한 번씩 다음을
수행합니다.

1. Account의 **Packages** page에서 package를 열고 **Package settings**를 선택합니다.
2. **Danger Zone**의 **Change visibility**에서 **Public**을 고르고 이름을 확인합니다.
3. 세 package에서 반복한 뒤 같은 실패 SHA의 release를 재실행합니다.

GitHub 공식 [Personal account visibility
절차](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility#configuring-visibility-of-packages-for-your-personal-account)는
public 전환을 되돌릴 수 없다고 안내합니다. 자동화는 이 작업을 의도적으로 수행하지 않습니다.
세 package가 모두 public이 될 때까지 workflow의 익명 검증이 실패합니다.

그 뒤 consumer는 credential 없이 검증된 digest를 우선해 pull합니다.

```bash
docker pull ghcr.io/leeyh0216/mystack-proxy@sha256:FULL_INDEX_DIGEST
```

GitHub [Package permission
안내](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages)는
public container package의 익명 접근을 설명합니다. Visibility 실패를 숨기기 위해 consumer token을
추가하지 않습니다.

<!-- section: vulnerability -->
## 취약점과 rollback 의미

이 프로젝트는 GHCR에서 ECR 방식 scan-on-push 계약을 사용하지 않습니다. Registry 인증 전에 local
platform image를 검사합니다. 검증, build, timeout, 근거 누락, 설정된 취약점 중 하나라도 실패하면
authorization을 만들지 않습니다. 진단용 raw `preflight-*` artifact는 남습니다.

Push 뒤 Glue runtime probe에도 상한을 둡니다. Nonzero exit, timeout, 잘못된 report가 발생하면
release를 멈추기 전에 published-release evidence artifact 아래에 실패한 `sqlite-runtime.json`을
작성합니다. Document에는 최대 4,096자인 redacted stdout/stderr tail만 남기며 전체 container output,
token, credential, query value는 넣지 않습니다. Probe가 실패해도 evidence upload를 수행하고 14일간
보존합니다.

취약점 판정 기준은 기본적으로 설정 severity를 모두 거부합니다. 알려진 upstream runtime finding은
`config/release/registry-release.json`의 정확한 항목으로만 허용할 수 있습니다. Component, CVE, package,
설치 version, image 상대 JAR path가 모두 일치하고 검토 날짜가 `expires_on`을 넘지 않아야 합니다.
Preflight 근거에는 raw count, 활성 count, 제한된 예외, 사유, 만료일, 출처가 남습니다. 만료되거나
조금이라도 다른 finding은 활성 상태가 되어 release를 차단합니다. 이는 Trivy 공식 [finding suppression
모델](https://trivy.dev/docs/latest/guide/configuration/filtering/)과 같은 위험 승인 개념이지만,
authorization artifact를 명시적이고 결정적으로 유지하기 위해 Mystack이 file 기반 coordinate를 직접
평가합니다.

현재 예외는 고정 Spark 3.5.4/EMR 7.8과 AWS Glue 5 profile에 포함된 dependency만 다룹니다. Glue
image에서는 scan 전에 Job 전용 Maven cache, Delta, Hudi, Flink, streaming, Redshift, 중복 PySpark JAR
surface를 제거합니다. 두 local emulator 모두 Derby LDAP authentication과 ZooKeeper quorum service를
시작하지 않습니다. Avro와 Parquet 결정은 해당 library가 안전하다는 의미가 아닙니다. Mystack에는
인증이나 multi-tenant 경계가 없고 EMR Step 제출자는 이미 임의의 operator-owned code를 실행할 수
있으며, 검증 가능한 수정 runtime을 고정할 때까지 Glue 입력은 신뢰할 수 있는 local dataset이어야
합니다. [Avro advisory](https://nvd.nist.gov/vuln/detail/CVE-2024-47561), [Parquet
advisory](https://nvd.nist.gov/vuln/detail/CVE-2025-30065), [Derby
advisory](https://nvd.nist.gov/vuln/detail/CVE-2022-46337), [ZooKeeper security
page](https://zookeeper.apache.org/security/)를 정책에 연결했습니다. Maintainer는 runtime을 patch하거나
새 만료일을 명시적으로 검토해야 하며 scan 통과를 위해 coordinate 범위를 넓혀서는 안 됩니다.

Rollback은 tag를 덮어쓰지 않고 consumer를 이전에 검증한 `image@sha256:...`로 바꿉니다. Snapshot
metadata에는 30일 보존 목표를 기록하지만 삭제는 아직 자동화하지 않습니다.

<!-- section: failures -->
## 실패 대응표

| Event 또는 실패 | 의미 | 변경 지점 |
| --- | --- | --- |
| `registry.preflight.record.*` | Local component/platform scan 통과 | Dockerfile, platform 또는 scan 정책 |
| `registry.gate.verify.*` | 전체 근거 set 검증 | 누락/추가 artifact, source SHA, version 또는 scan 결과 |
| Immutable binding 충돌 | 기존 image revision 불일치 | 버전을 올리고 덮어쓰지 않음 |
| Push 중 package permission 거부 | Workflow와 package 연결 불일치 | Workflow permission과 package access |
| 익명 검증 거부 | Package가 아직 private | 1회성 visibility 변경 후 같은 SHA 재실행 |
| `registry.index.verify.failed` | Runtime platform 누락 | Dockerfile base manifest 또는 설정 platform |
| `glue.sqlite.preflight.failed` | 게시한 Glue platform digest가 SQLite runtime을 증명하지 못함 | 보존한 redacted `sqlite-runtime.json`, Dockerfile dependency resolver, runtime policy 확인 |
| `registry.scan.exception.matched` | 정확히 검토한 finding의 한시 허용 | Coordinate, 사유, 출처, 만료일 검토 |
| `registry.scan.exception.expired` | Risk decision 검토 기한 도달 | Runtime patch 또는 검토 후 새 버전으로 갱신 |
| `registry.scan.evaluate.failed` | 승인하지 않은 설정 severity finding 존재 | Runtime/base를 고치고 새 버전 사용 |
| Image 게시 후 GitHub Release 없음 | 마지막 transaction step 실패 | 같은 SHA를 재실행해 일치하는 tag/image 이어서 처리 |

Log는 side effect 경계에 구조화된 `.before`, `.after`, `.failed` event를 사용합니다. Token, 전체
environment 값, image layer는 기록하지 않습니다.

<!-- section: local-checks -->
## 게시하지 않는 local 검사

```bash
make version-check
make registry-check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 \
  .github/workflows/ci.yml \
  .github/workflows/release.yml \
  .github/workflows/container-publish.yml \
  .github/workflows/prepare-version-pr.yml
```

이 검사는 push하지 않습니다. 성공한 post-CI `develop` 또는 `main` 게시만 package write token을
받습니다.
