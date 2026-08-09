<!-- doc-id: versioning -->
<!-- lang: ko -->

[한국어](versioning.ko.md) | [English](versioning.md)

# 버전과 브랜치 전달 흐름

<!-- toc:start -->
## 목차

- [Local 명령](#local-명령)
- [GitHub UI 흐름](#github-ui-흐름)
- [Branch와 event 정책](#branch와-event-정책)
- [게시 transaction](#게시-transaction)
- [Repository ruleset](#repository-ruleset)
- [실패와 복구 대응표](#실패와-복구-대응표)
- [지원 및 제외 정책](#지원-및-제외-정책)
<!-- toc:end -->

이 문서는 `feature/*` → `develop` → `main` 흐름을 관리하는 개발자를 위한 안내입니다. Commit하는
버전 원천은 `VERSION` 하나입니다. 이 파일에는 `1.4.0` 같은 안정된 [Semantic
Versioning](https://semver.org/) core만 넣으며 snapshot suffix는 commit하지 않습니다.

<!-- section: commands -->
## Local 명령

```bash
make version-show
make version-check
make version-bump PART=patch
make version-bump PART=minor VERSION_ARGS=--dry-run
uv run python scripts/release/version.py set 1.4.0
uv run python scripts/release/version.py check --base-ref origin/main
```

`version-bump`와 `set`은 `config/release/version-files.json`에 선언한 모든 파일을 바꾸고 unified diff를
출력하며 working tree가 변경된 상태이면 중단합니다. `--dry-run`은 파일을 쓰지 않습니다.
`--allow-dirty`는 통제된 자동화에서만 사용합니다. 이 명령은 commit, push, tag, image 게시,
release 생성을 수행하지 않습니다. Python snapshot 버전은 공식 [PEP 440 version
규칙](https://packaging.python.org/en/latest/specifications/version-specifiers/)을 사용하고 공개 OCI
tag는 문서화한 SemVer 파생 형식을 유지합니다.

동일한 local Git 흐름은 다음과 같습니다.

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
## GitHub UI 흐름

**Actions**에서 **Prepare version PR**을 선택하고 **Run workflow**에서 `patch`, `minor`, `major`,
`exact` 중 하나를 고릅니다. `exact`이면 안정된 `X.Y.Z`를 입력하고 나머지는 exact-version 입력을
비웁니다. Workflow가 `prepare/version-*` branch를 만들고 `develop` 대상 PR을 엽니다. Package
permission이 없으므로 게시할 수 없습니다. 이 절차는 GitHub 공식 [수동 workflow 실행
안내](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/manually-running-a-workflow)를
따릅니다.
Repository 기본 token은 제한된 read-only 상태를 유지하고 이 job만 `contents`와 `pull-requests`
write를 요청합니다. GitHub [Workflow permission
설정](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository?apiVersion=2022-11-28)에서
Actions의 pull request 생성을 허용해야 합니다. Workflow는 자신이 만든 PR을 승인하거나 merge하지
않습니다.

<!-- section: branches -->
## Branch와 event 정책

| Event | 결과 | 변경 |
| --- | --- | --- |
| `develop` 또는 `main` 대상 PR | build, test, version 검증 | 없음 |
| `feature/*` push | build와 test | 없음 |
| `develop` push의 CI 성공 | `vX.Y.Z-snapshot.RUN.gSHA8` | 세 GHCR image만 게시 |
| `main` push의 CI 성공 | `vX.Y.Z` | annotated tag, 전체 image, GitHub Release |
| CI 실패, PR에서 시작한 CI, 수동 CI, 다른 branch | 거부 | 없음 |

권한 없는 CI workflow는 `contents: read`만 사용합니다. 게시는 GitHub의 [`workflow_run` 완료
event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)에서만
시작하며 source event, workflow name, branch, conclusion, 정확한 head SHA를 다시 검사합니다.
Reusable workflow 권한은 GitHub [permission
모델](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)을
따릅니다. Image job만 `packages: write`, annotated tag와 release job만 `contents: write`를 받습니다.

<!-- section: transaction -->
## 게시 transaction

모든 job이 승인된 정확한 SHA를 checkout합니다. Repository contract와 release acceptance case를
실행한 뒤 local multi-platform build와 고정 Trivy 검사를 수행합니다. Content hash를 가진 aggregate
authorization이 설정의 모든 component/platform 조합을 포함해야 합니다. 정식 게시에서는 GitHub가
문서화한 2단계 [tag object와 tag reference
API](https://docs.github.com/en/rest/git/tags)로 annotated tag를 만들고 Proxy, EMR, Glue를 게시합니다.
Registry 로그인을 하지 않은 상태에서 OCI platform과 revision label을 검증한 다음 공식 [Releases
API](https://docs.github.com/en/rest/releases/releases)로 자동 생성 note를 포함한 GitHub Release를
마지막에 만듭니다.

`latest`는 게시하지 않습니다. Snapshot과 정식 tag는 정책상 변경하지 않습니다. 재실행은 기존
tag target 또는 image revision label이 원래 SHA와 같을 때만 이어서 처리합니다. 다른 SHA이면
덮어쓰기 전에 실패합니다. 정식 release는 마지막에 만들기 때문에 익명 검증에 실패한 image를
정상 release로 알리지 않습니다.

Snapshot 보존 기간은 `config/release/registry-release.json`과 실행별 `retention.json`에 30일로 기록합니다.
삭제 자동화는 아직 없으며 정식 image는 snapshot 정리 대상이 아닙니다.

<!-- section: governance -->
## Repository ruleset

GitHub [repository
ruleset](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)으로
두 branch를 다음과 같이 설정합니다.

- `main`: PR 전용, linear history, 삭제와 force push 금지, `Required CI` 필수
- `develop`: PR 권장, linear history, 삭제와 force push 금지, `Required CI` 필수
- `feature/*`: 게시 workflow trigger와 package write token 없음

승인 인원은 repository owner가 선택하며 코드에 고정하지 않습니다. Concurrency는 branch별 게시를
직렬화하고 version 및 immutable binding 검사가 오래된 PR과 재시도를 최종 방어합니다.

검토 가능한 원천은 `config/governance/github-rulesets.json`입니다. 승인 수는 설정에서 선택하며 현재
single-maintainer repository 기본값은 0입니다. 다음 명령으로 Mystack이 소유한 ruleset 두 개만
검증하거나 수렴시킵니다.

```bash
make rulesets-check
make rulesets-apply REPOSITORY=leeyh0216/mystack DRY_RUN=--dry-run
make rulesets-apply REPOSITORY=leeyh0216/mystack
```

Apply 명령은 정확한 관리 name으로 ruleset을 만들거나 갱신하며 관련 없는 ruleset을 삭제하거나
바꾸지 않습니다. Repository administration permission이 필요하고 공식 [Repository ruleset REST
API](https://docs.github.com/en/rest/repos/rules)를 사용합니다.

<!-- section: recovery -->
## 실패와 복구 대응표

| 실패 또는 event | 의미 | 복구 방법 |
| --- | --- | --- |
| `version.drift.check` | 파생 파일과 `VERSION` 불일치 | `make version-check`로 확인하고 의도한 버전으로 `version.py set` 실행 |
| `release.policy.failed` | Event, ref, source workflow가 게시 불가 | 일반 PR을 사용하고 CI에 write 권한을 추가하지 않음 |
| `github.tag.ensure.*` | 정식 tag 생성 또는 같은 SHA 재개 | 같은 SHA의 실패한 release를 재실행 |
| Immutable binding 충돌 | Tag 또는 image가 다른 SHA 소유 | `VERSION`을 올리고 기존 tag를 덮어쓰지 않음 |
| 일부 image만 게시 | 같은 SHA의 일부 component만 존재 | 같은 workflow를 재실행하면 일치하는 image를 검증하고 건너뜀 |
| 익명 검증 거부 | GHCR package가 public이 아님 | `container-release.ko.md`의 1회성 visibility 절차 후 재실행 |
| `registry.index.verify.failed` | OCI platform set과 설정 불일치 | Dockerfile 또는 base index를 고치고 새 버전 게시 |
| Release 생성 실패 | Image는 통과했으나 GitHub Release 없음 | 같은 SHA를 재실행하면 tag와 image를 안전하게 이어서 처리 |

모든 외부 명령에는 timeout이 있습니다. 경계 log에는 action, branch, version, component, revision,
복구 안내를 남기지만 token은 기록하지 않습니다. Actions artifact에서 preflight scan, aggregate
authorization, 게시 index, retention metadata를 확인합니다.

<!-- section: support -->
## 지원 및 제외 정책

이 자동화는 설정된 Linux `amd64`/`arm64`용 component image 세 개를 GHCR에 게시하고 정식 GitHub
tag와 release를 만듭니다. Python/npm package, `latest`, component별 수동 release, registry mirror,
서명된 Git tag, snapshot 자동 삭제, 실 AWS artifact는 게시하지 않습니다. 이 항목을 추가하면
release 계약이 달라지므로 별도 issue, 설정 schema 변경, test, 한·영 문서가 필요합니다.
