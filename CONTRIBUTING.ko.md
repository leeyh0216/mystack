<!-- doc-id: contributing -->
<!-- lang: ko -->

[한국어](CONTRIBUTING.ko.md) | [English](CONTRIBUTING.md)

# Mystack 기여 안내

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

<!-- section: issues -->
## 이중 언어 이슈

모든 이슈 본문에는 같은 내용을 담은 `## English`와 `## 한국어` 구역이 있어야
합니다. 범위, 완료 조건, 제외 범위, 의존성, 공식 출처를 두 언어에서 동일하게
유지합니다. 제목은 영어만 사용해도 됩니다. GitHub의 이슈 작성 기능은 [GitHub
Issues 문서](https://docs.github.com/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)를
참고합니다.

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
