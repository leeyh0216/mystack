# 프로젝트 기준선

한국어 | [English](baseline.md)

## Metadata

- 상태: 승인됨, 지속 갱신
- 소유자: leeyh0216
- 갱신일: 2026-08-08
- 저장소: private `leeyh0216/mystack`

## 목적

Mystack은 Docker 친화적인 EMR·Glue Data Catalog protocol emulator입니다. LocalStack 앞의 투명하고 확장 가능한 Proxy를 사용하며 실제 Spark 3.5.x EMR Step을 local mode로 실행합니다.

Glue Job, JobRun, Crawler API는 제외합니다. Glue 범위는 Data Catalog, Glue/Hive 타입, Hive 상호운용, Iceberg입니다.

## 구현 기준 사실

- 독립 패키징된 `shared`, `proxy`를 가진 Python uv workspace
- 서비스와 operation fingerprint를 포함한 고정 botocore model contract manifest
- AWS JSON 1.1 request 검증·dispatch·성공·modeled error codec
- 설정만으로 확장하는 Proxy route registry와 투명 LocalStack fallback
- 범용 nested 환경변수 override를 지원하는 versioned YAML 설정
- payload 원문/Authorization 없이 hash·length를 기록하는 구조화 경계 로그
- 선택적 Bearer token을 지원하는 thread·asyncio task 진단 endpoint
- GitHub milestone, 한·영 이슈, Python CI, model drift, Docker E2E, ECR workflow
- 이 기준선 시점 shared/Proxy 테스트 12개 통과

## Entry point와 명령

- Proxy executable: `mystack-proxy`
- 설정: `config/mystack.yaml`
- Workspace 설치: `uv sync --locked --all-packages`
- Unit/contract test: `uv run pytest -m "not e2e" --timeout 60`
- CI: `.github/workflows/ci.yml`
- 정기 model drift: `.github/workflows/model-drift.yml`
- Docker E2E: `.github/workflows/e2e.yml`

## 확정 결정

- EMR 장기 목표는 public API 광범위 호환입니다.
- Glue 목표는 Data Catalog public API이며 Job, JobRun, Crawler는 계획하지 않습니다.
- 오류는 AWS 버그가 아니라 문서화된 검증, exception code, HTTP status, 상태 동작, side effect를 재현합니다.
- 하위 모듈은 상위 모듈을 알지 않으며 Domain은 API·저장소·Spark·Docker와 독립적입니다.
- 모든 문서는 한글·영문 쌍과 직접적인 공식 출처를 포함합니다.
- 모든 side effect 경계는 비밀정보 없이 전·후·오류를 기록합니다.
- 모든 테스트 계층은 설정 가능한 timeout을 명시하고 E2E는 public Proxy endpoint를 사용합니다.

## 주요 미구현 Gap

- EMR Domain/control-plane 상태 머신, bootstrap runner, S3 resolver, Spark runner
- Glue Data Catalog 저장과 operation 의미 구현
- Spark Hive/Iceberg catalog 통합
- Docker Compose runtime, public endpoint boto3 E2E, 관리 UI
- operation별 생성형 호환성 matrix

## 공식 참고 자료

- [Amazon EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue Web API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [공식 botocore 모델](https://github.com/boto/botocore/tree/develop/botocore/data)
- [AWS Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
- [AWS SDK custom endpoint](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)

