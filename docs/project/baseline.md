# Project Baseline

## Metadata
- status: approved
- owner: leeyh0216
- updated_at: 2026-08-08
- approved_by: leeyh0216
- approved_at: 2026-08-08

## 프로젝트 개요
- 프로젝트명: Mystack (GitHub 저장소: `leeyh0216/mystack`)
- 목적: LocalStack 앞단에서 AWS EMR/Glue API 요청을 호환 처리하고, 실제 로컬 Spark 작업으로 실행하는 에뮬레이션 환경 구축
- 주요 실행 환경: Docker Compose, Python/FastAPI, Apache Spark 3.5.x, LocalStack S3/ECR

## 코드 기준 사실
- 주요 모듈/디렉터리: 구현 없음. 스캔 시작 시 작업 디렉터리가 비어 있었음.
- 엔트리포인트: 없음
- 빌드 명령: 없음
- 테스트 명령: 없음
- CI 경로: 없음

## UseCase 요약
- 참조 문서: `docs/project/usecase-catalog.md`
- 추출된 확정 UseCase 수: 0
- High 신뢰도 UseCase: 없음
- Medium/Low 신뢰도 UseCase: 없음
- 즉시 후보 기능 Gap: AWS 호환 Proxy, EMR Step/Spark 실행, Glue Job/Spark 실행, Bootstrap Action, S3 연동, Hive/Iceberg, 관찰 UI

## 문서 기준 사실
- 핵심 문서 목록: 이 기준선과 UseCase 카탈로그 외 기존 문서 없음
- 문서에 정의된 아키텍처/규칙: 사용자 요청 외 확정 문서 없음
- 문서에 정의된 운영 절차: GitHub 저장소, 마일스톤, 이슈, 커밋/푸시 기반 진행 요청

## 충돌/드리프트
- 코드와 문서가 불일치하는 항목: 비교할 기존 코드/문서 없음
- 영향 범위: 없음
- 확인 필요 근거 파일: 없음

## 미확정 항목
- 근거가 부족한 항목: 상태 저장 방식, LocalStack API를 보완할지 완전히 대체할지, UI 초기 범위
- 확인이 필요한 질문: 없음. 세부 구현 선택은 공식 프로토콜 및 API 모델을 기준으로 결정

## 사용자 확인/보정 결과
- 질문 로그(순차, 1회 1문항):
  - Q1
    - 내 분석(근거): 요구사항은 AWS CLI/boto 호환을 요구하지만 EMR/Glue 전체 API 표면은 매우 넓어 첫 릴리스의 명시적 호환 경계가 필요함.
    - 배경 요약: EMR 핵심 흐름은 클러스터 생성·조회·Step 제출/취소이며, Glue 핵심 흐름은 Job 생성·실행·조회/중단이다. Spark 3.5.x, S3(LocalStack), bootstrap, Hive/Iceberg, Docker/ECR, UI가 함께 요구되었다.
    - 확인 포인트: MVP를 핵심 실행 API에 집중할지, 처음부터 광범위한 AWS API를 목표로 할지 결정
    - 질문: 첫 릴리스의 API 호환 범위를 어디까지 보장할까요?
    - 사용자 답변: C. 공개 API의 광범위한 호환을 목표로 하며, 공식 문서와 프로토콜을 기준으로 구현한다. 오류 호환은 버그 재현이 아니라 문서화된 예외 코드와 동작(예: 중복 파티션의 AlreadyExistsException)을 뜻한다. Glue Crawler는 제외하고 Glue 지원 타입, Hive/Iceberg를 포함한다. 객체지향적으로 모듈화하며 하위 모듈이 상위 모듈에 의존하지 않게 한다.
    - 반영 내용: 전체 호환을 장기 목표로 확정하고 Crawler API를 명시적으로 제외했다. 프로토콜/서비스 모델 기반 계약 테스트, 오류 의미론, 타입 호환, 의존성 역전 원칙을 필수 제약으로 추가했다.

## 다음 단계 권장사항
1. 공식 프로토콜/서비스 모델 분석 및 지원 매트릭스 작성
2. 아키텍처 결정 기록과 GitHub 마일스톤/이슈 생성
3. Contract test부터 작성한 뒤 Proxy, EMR, Glue, UI 순으로 수직 구현
