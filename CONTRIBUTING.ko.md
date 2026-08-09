<!-- doc-id: contributing -->
<!-- lang: ko -->

[한국어](CONTRIBUTING.ko.md) | [English](CONTRIBUTING.md)

# Mystack 기여 안내

<!-- toc:start -->
## 목차

- [구현 전에 범위 정하기](#구현-전에-범위-정하기)
- [아키텍처 규칙](#아키텍처-규칙)
- [출처와 호환성 규칙](#출처와-호환성-규칙)
- [한·영 문서](#한영-문서)
- [시험과 제한 시간](#시험과-제한-시간)
- [테스트 선언 호환성 근거](#테스트-선언-호환성-근거)
- [이중 언어 이슈](#이중-언어-이슈)
- [이슈 단위 변경과 게시](#이슈-단위-변경과-게시)
- [변경 설명](#변경-설명)
<!-- toc:end -->

<!-- section: scope -->
## 구현 전에 범위 정하기

AWS 동작을 구현하기 전에 공개 작업, 요청과 응답 구조, 상태 전이, 오류 코드를 먼저
정합니다. [Amazon EMR API
Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html), [AWS Glue
Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html), [고정된
botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data)에서
근거를 찾습니다. 구현, 시험, 문서 가까이에 정확한 공식 링크를 둡니다.

AWS 서비스 오류를 Mystack 구현 결함과 구분합니다. 예를 들어 기존 파티션을 다시
만들 때 반환되는 `AlreadyExistsException`은 재현해야 할 서비스 계약입니다.

<!-- section: architecture -->
## 아키텍처 규칙

- 도메인과 애플리케이션 계층은 FastAPI, boto3, Spark, Docker, 저장소 구현을 알지
  못해야 합니다.
- 외부 시스템과 사용자 확장은 안정적인 포트 또는 공개 확장 API 뒤에 둡니다.
- 불변 조건과 상태 전이는 애플리케이션 계층에서 지킵니다. 어댑터나 확장 코드가
  저장 구현을 직접 수정하지 않게 합니다.
- 지원하지 않는 필드는 조용히 무시하지 않습니다. 공식 오류 구조로 거부합니다.
- 설정은 버전이 있는 파일 모델, 기본값, 유효성 검사, 예제를 함께 수정합니다.
- 부수 효과의 전·후·오류 로그를 남깁니다. 인증 정보와 요청 본문 원문은 남기지
  않습니다.

자세한 의존성 규칙은 [AWS Hexagonal architecture
지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)과
이 저장소의 [아키텍처 문서](docs/architecture.ko.md)를 참고합니다.

<!-- section: provenance -->
## 출처와 호환성 규칙

- 서비스 계약에는 AWS의 1차 출처를 사용합니다.
- SDK 동작에는 시험한 botocore 버전과 서비스 모델 지문을 기록합니다.
- Spark, Hive, Iceberg 동작에는 정확한 배포 버전의 공식 문서나 소스 태그를
  연결합니다.
- 관찰한 클라우드 응답은 민감정보를 제거한 검증 자료로 저장합니다.
- 호환성 보완 코드에는 적용 버전, 수정 위치 안내, 제거 조건을 기록합니다.

<!-- section: bilingual-docs -->
## 한·영 문서

유지보수 문서를 바꿀 때는 같은 변경에서 한국어와 영어 파일을 함께 수정합니다.

- `README.md`와 `README.ko.md`
- `CONTRIBUTING.md`와 `CONTRIBUTING.ko.md`
- `docs/name.md`와 `docs/name.ko.md`

두 파일은 같은 `doc-id`, 같은 순서의 `section` 표식, 같은 공식 출처 URL을
사용합니다. 각 페이지에는 언어 전환 링크를 둡니다. 한국어 문서는 [한국어 기술 문서
작성 기준](docs/korean-writing-style.ko.md)을 따릅니다.

<!-- section: tests -->
## 시험과 제한 시간

가장 가까운 계층의 시험부터 실행한 뒤 전체 계약 시험을 실행합니다.

```bash
make docs
make contract
make e2e
```

정상 동작, 공식 오류, 상태 전이, 경계값을 함께 검증합니다. 공개 프로토콜은 boto3와
AWS CLI로 확인합니다. Spark 연동은 실제 Spark, Glue Catalog, Hive, Iceberg 실행
경로에서 확인합니다. 모든 시험에는 명시적인 제한 시간을 둡니다. CI와 로컬 명령의
자세한 값은 [시험 전략](docs/testing.ko.md)을 참고합니다.

<!-- section: compatibility-evidence -->
## 테스트 선언 호환성 근거

호환성 근거는 세 경계가 맡습니다.

- EMR/Glue inbound operation 목록은 구현 상태를 맡습니다.
- annotation을 붙인 `contract` 또는 `e2e` 시험은 실제로 검증한 정확한 client, runtime,
  scenario, operation, capability, support claim을 맡습니다.
- `compatibility/cases.yaml`과 `contracts/api-coverage.json`은 이행 기간의 parity 기준으로
  남깁니다. Glue 오류 조건 catalog와 우선순위 정책은 별도의 필수 계약으로 유지합니다.

Collection은 annotation operation 합집합과 code가 소유한 EMR/Glue dispatcher inventory의 literal
값이 같은지 확인합니다. Annotation만으로 등록되지 않은 operation을 compatible로 만들 수 없으며,
botocore만 설치한 model-drift job도 emulator import 없이 이 literal inventory를 읽습니다.

Client 또는 runtime을 바꿀 때는 다음 순서를 사용합니다.

1. `test_support/compatibility_profiles.py`에서 정확한 version, runtime, lane,
   GitHub Actions job 실행 시간 상한, 공식 출처 URL을 가진 `CompatibilityProfile`을 만들거나 재사용합니다.
2. 가장 작은 실제 `@pytest.mark.contract` 또는 `@pytest.mark.e2e` 시험에
   `@compatibility_evidence(...)`를 붙입니다. 그 test body가 실행하는 operation과 scenario만
   선언합니다.
3. `make compatibility-evidence-generate`를 실행하고
   `contracts/compatibility-evidence.generated.json`과 한·영 표를 검토한 뒤
   `make compatibility-evidence-check`를 실행합니다.
4. 바꾼 case에 `make compatibility-case CASE=<id>`를 실행합니다. 이행 기간에는
   `make compatibility-check`도 실행합니다. 생성한 근거를 직접 수정하거나 두 기준 파일을
   제거하지 않습니다.

가장 작은 annotation은 증명하는 test 가까이에 둡니다.

```python
import pytest

from test_support.compatibility import compatibility_evidence
from test_support.compatibility_profiles import BOTO3_BOTOCORE_CONTRACT


@pytest.mark.contract
@compatibility_evidence(
    BOTO3_BOTOCORE_CONTRACT,
    scenario_ids=("glue-get-database",),
    operations={"glue": ("GetDatabase",)},
    capabilities=("glue-database-read",),
)
def test_get_database() -> None:
    ...
```

Generator는 pytest를 `--collect-only`로 호출합니다. Test body를 실행하지 않고 marker와 node ID를
결정합니다. 실행 marker, 고정 lock/runtime, API 근거, 기존 case 선택 중 하나라도 달라지면 실패합니다.
[pytest marker](https://docs.pytest.org/en/stable/how-to/mark.html)와 [collection
호출](https://docs.pytest.org/en/stable/how-to/usage.html) 계약, GitHub Actions의 [공유 matrix
방식](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)을
따릅니다.
로컬 확인 비용을 낮추기 위해 timeout/asyncio plugin만 명시적으로 불러오며, collection 중
`awswrangler` 또는 `pyarrow` import가 발생하면 실패합니다. 선택 client는 test body 안에서만
import해야 합니다. 이는 pytest의 [plugin loading 제어](https://docs.pytest.org/en/stable/how-to/plugins.html#disabling-plugin-autoloading)를
따릅니다.
`CompatibilityProfile.expected_duration_minutes`는 GitHub Actions 바깥 job의 실행 시간 상한입니다.
pytest timeout이 아닙니다. Collection subprocess는
`tests.compatibility_collection_timeout_seconds`로 제한하고, 선택한 test body는 기존 contract 또는
E2E YAML timeout을 사용합니다.

| 실패 종류 | 수정 위치 |
| --- | --- |
| Marker/profile 구조 또는 execution marker | annotation을 붙인 test와 `test_support/compatibility.py` |
| Claim한 operation이 구현 inventory에 없음 | 소유한 `emr` 또는 `glue` `adapters/inbound/aws_*.py` registry와 test annotation |
| Operation이 고정한 botocore model에 없음 | inbound handler, 고정 model 검토, test annotation |
| Lock client/runtime 불일치 | `uv.lock`, `test_support/compatibility_profiles.py`, `config/mystack.yaml` |
| Collection 제한 시간 초과 | `tests.compatibility_collection_timeout_seconds` 또는 annotation test collection 중 import한 항목 |
| 생성 output 차이 | `make compatibility-evidence-generate` 실행; 생성 file을 직접 수정하지 않음 |

<!-- section: issues -->
## 이중 언어 이슈

모든 이슈 본문에는 같은 내용을 담은 `## English`와 `## 한국어` 구역이 있어야
합니다. 범위, 완료 조건, 제외 범위, 의존성, 공식 출처를 두 언어에서 동일하게
유지합니다. 제목은 영어만 사용해도 됩니다. GitHub의 이슈 작성 기능은 [GitHub
Issues 문서](https://docs.github.com/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)를
참고합니다.

<!-- section: workflow -->
## 이슈 단위 변경과 게시

- 구현 전에 이중 언어 이슈를 만들고 milestone과 분류 label을 지정합니다.
- `develop`에서 `feature/<issue>-<topic>` branch를 만들고 구현 PR도 `develop`으로 엽니다. 검토한
  변경 묶음은 새 정식 version과 함께 있을 때만 `develop`에서 `main`으로 전달합니다.
- 한 이슈의 구현, 시험, 사용자 문서와 유지보수 문서를 함께 완료합니다.
- 완료한 변경을 working tree에 누적하지 않습니다. Local 검사를 통과하면 이슈 번호를 참조하는
  하나의 논리적 commit을 만들고 feature branch를 push한 뒤 CI 결과를 확인합니다.
- 완료 조건과 CI를 모두 확인한 뒤 이슈를 닫습니다. 다음 관심사는 새 이슈와 commit으로
  분리합니다.

PR과 feature branch는 게시할 수 없습니다. 반영된 `develop` commit의 CI가 성공하면 고유 snapshot,
반영된 `main` commit의 CI가 성공하면 정식 version을 게시합니다. [Version
안내](docs/versioning.ko.md)를 따르고 release tag를 직접 만들지 않습니다.

GitHub의 [commit으로 이슈 닫기
기능](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)을
사용할 수 있습니다.

<!-- section: change-description -->
## 변경 설명

풀 리퀘스트에는 다음 정보를 씁니다.

- 지원하는 클라이언트와 실행 환경 버전
- 관련 공식 문서와 서비스 모델
- 선택한 계층과 의존성 방향
- 정상 동작과 오류 동작
- 구조화 로그와 진단 위치
- 실행한 시험과 제한 시간
- 남은 제약과 후속 작업

완료 조건을 모두 확인하기 전에는 이슈를 닫지 않습니다.
