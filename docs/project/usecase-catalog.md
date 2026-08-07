# UseCase Catalog

## Metadata
- status: approved
- owner: leeyh0216
- updated_at: 2026-08-08
- approved_by: leeyh0216
- approved_at: 2026-08-08

## 추출 범위
- 스캔 기준 경로: `/Users/leeyh0216/Documents/project/ministack-enhanced`
- 포함 범위: 기존 코드, 문서, 빌드/테스트/CI 설정
- 제외 범위: 아직 작성되지 않은 구현
- 근거 우선순위: 코드 > 테스트 > 최근 커밋/PR > 문서

## UseCase 목록

현재 구현 근거가 없어 확정 UseCase는 없다.

## 후보 기능 기회(UseCase Gap)
- Gap-001: AWS SDK/CLI 호환 Proxy
  - 현재 상태: 구현 없음
  - 문제/제약: AWS JSON RPC/Query 요청의 서비스 판별, SigV4 헤더/본문 보존, 미지원 API의 LocalStack 전달 정책이 미확정
  - 후보 기능: EMR/Glue 요청은 전용 에뮬레이터로, 그 외 서비스는 LocalStack으로 투명 전달
  - 예상 입력/출력 변화: AWS CLI/boto 요청을 받아 AWS 형식 응답 또는 오류 반환
  - 근거: 사용자 요구사항

- Gap-002: EMR 클러스터와 Step 실행
  - 현재 상태: 구현 없음
  - 문제/제약: 실제 분산 EMR가 아닌 Spark local mode에서 상태 머신과 프로세스 격리를 재현해야 함
  - 후보 기능: 클러스터 생성/조회/종료, bootstrap action, Step 제출/취소, S3 아티팩트 다운로드, Spark 3.5.x local 실행
  - 예상 입력/출력 변화: EMR API 입력을 받고 AWS 호환 식별자/상태/오류 및 Spark 로그 생성
  - 근거: 사용자 요구사항

- Gap-003: Glue Job 실행
  - 현재 상태: 구현 없음
  - 문제/제약: Glue 버전별 라이브러리와 오류 전체를 완전히 동일하게 재현하는 것은 공식 런타임과의 계약 테스트가 필요함
  - 후보 기능: Job CRUD, JobRun 시작/조회/중단, Spark 3.5.x 실행, Glue 호환 인자, Hive Metastore와 Iceberg 카탈로그 지원
  - 예상 입력/출력 변화: Glue API 입력을 받고 AWS 호환 상태/오류 및 Spark 로그 생성
  - 근거: 사용자 요구사항

- Gap-004: LocalStack S3/ECR 연동
  - 현재 상태: 구현 없음
  - 문제/제약: path-style S3 endpoint, 자격 증명, 컨테이너 네트워크, ECR 이미지 식별/실행 정책 필요
  - 후보 기능: 스크립트/JAR/bootstrap 다운로드와 사용자 지정 런타임 이미지 실행
  - 예상 입력/출력 변화: S3 URI와 ECR image URI를 실행 가능한 로컬 자산/컨테이너로 변환
  - 근거: 사용자 요구사항

- Gap-005: AWS Console 유사 UI
  - 현재 상태: 구현 없음
  - 문제/제약: 핵심 실행 호환성과 독립적으로 범위를 제한해야 함
  - 후보 기능: EMR 클러스터/Step, Glue Job/Run, 상태/로그 조회 대시보드
  - 예상 입력/출력 변화: 브라우저에서 리소스 조회 및 실행/중단 조작
  - 근거: 사용자 요구사항

## 승인된 범위 제약
- 장기 목표는 EMR/Glue 공개 API의 광범위한 호환이다.
- 구현 계약의 단일 기준은 AWS 공식 문서, 공식 SDK 서비스 모델 및 명시된 wire protocol이다.
- 오류 호환은 서비스 버그가 아니라 입력 검증, 리소스 상태, 예외 타입/코드, HTTP 상태 및 AWS 오류 응답 형태를 뜻한다.
- Glue Crawler는 범위에서 제외한다.
- Glue 지원 타입과 Data Catalog 의미론, Hive/Iceberg 통합을 범위에 포함한다.
- 내부 구조는 의존성 역전을 적용해 Domain이 Application/Adapter/API 계층을 알지 않도록 한다.
