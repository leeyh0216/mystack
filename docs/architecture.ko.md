<!-- doc-id: architecture -->
<!-- lang: ko -->

[한국어](architecture.ko.md) | [English](architecture.md)

# 아키텍처

<!-- section: goals -->
## 목표

Mystack은 AWS API 경계에서 관찰되는 EMR 및 Glue Data Catalog 동작을 에뮬레이션하고 실제 Spark 작업을 로컬에서 실행합니다. 프로토콜, 상태 전이, 검증, 오류, 로그, side effect를 모두 계약으로 취급합니다.

<!-- section: boundaries -->
## 시스템 경계

| 컴포넌트 | 책임 | 알면 안 되는 것 |
| --- | --- | --- |
| `proxy` | AWS 서비스 판별과 HTTP 교환의 투명 전달 | EMR/Glue 도메인 규칙과 저장 방식 |
| `emr` | EMR 리소스, 클러스터/Step 상태 머신, bootstrap/Spark 실행 | Proxy 라우팅과 Glue 모델 |
| `glue` | Glue Data Catalog, Glue 타입, Hive/Iceberg 상호운용성 | Proxy 라우팅과 EMR 모델 |
| `shared` | AWS JSON 1.1 codec, 공식 서비스 모델, 요청 검증 | EMR/Glue 비즈니스 규칙 |

Proxy route registry는 설정 기반입니다. 새 emulator는 target prefix, SigV4 signing name, host prefix, backend URL만 등록하며 Proxy 코드를 변경하거나 새 서비스 패키지를 import하지 않습니다.

Composition root는 사용자 provider를 찾고 Glue가 소유한 세 context 중 하나를 주입합니다.
공통 작업 chain은 `OperationMiddleware`만 알며 Glue capability나 사용자 package를 import하지
않습니다. 자세한 내용은 [확장 SPI 안내](extensions.ko.md)를 참고합니다.

<!-- section: dependencies -->
## 의존성 규칙

두 emulator 모두 다음 방향만 허용합니다.

```text
domain <- application <- adapters <- bootstrap / FastAPI app
```

- Domain: entity, value object, 상태 머신, domain exception, repository port
- Application: use case와 orchestration; Domain과 내부에서 선언한 port에만 의존
- Adapter: AWS JSON 입력, 저장소, S3, Spark/process 구현
- Composition root: concrete dependency와 FastAPI route 구성

CI의 architecture test가 안쪽 계층에서 바깥 계층으로 향하는 import를 거부합니다. 이는 AWS의 [Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)을 적용한 것입니다.

<!-- section: topology -->
## 실행 토폴로지

```text
host:4566 -> proxy:8080
                |-- ElasticMapReduce.* -> emr:8080
                |-- AWSGlue.*          -> glue:8080
                `-- 기타 모든 요청    -> localstack:4566
```

EMR은 emulated cluster별 Spark local process를 실행합니다. Glue Job/JobRun은 구현하지 않으며 Spark 기반 Glue Catalog/Hive/Iceberg 검증은 versioned runtime profile에서 실행합니다.

Management traffic은 별도 outward read-model 경계를 사용합니다. 각 service의 inbound
management adapter가 Application/Domain resource를 versioned JSON으로 변환하고 Proxy가 이를
전달하며 browser UI는 service 내부를 import하지 않고 렌더링합니다. 자세한 내용은
[관리 Console 계약](console.ko.md)을 참고하세요.

<!-- section: compatibility -->
## 호환성 전략

1. 작업, 요청과 응답 구조, 열거형, 예외의 기준이 되는 공식 botocore 모델 버전을 고정합니다.
2. 전체 model과 operation별 fingerprint를 contract manifest에 기록합니다.
3. boto3/AWS CLI로 실제 endpoint 직렬화 계약을 테스트합니다.
4. 상태와 오류 의미론을 별도 contract test로 검증합니다.
5. 최신 botocore와의 차이를 매주 검사하고 변경 operation과 수정 위치를 이슈로 보고합니다.
6. Spark/Hive/Iceberg 조합은 runtime profile별 E2E matrix로 검증합니다.

호환 오류란 문서화된 exception type, HTTP status, error code, 관련 message field, side effect 유무가 일치함을 뜻하며 AWS의 미문서화 버그를 재현한다는 뜻이 아닙니다.

<!-- section: logging -->
## 로깅

Controller 진입/종료, route 판정, 상태 전이, 저장소/S3/process side effect 전후와 오류를 구조화 JSON으로 기록합니다. Authorization과 payload 원문은 제외하고 request ID, operation, 모델 버전/fingerprint, payload 길이/해시, duration, 상태를 기록합니다. 모델 불일치 로그에는 수정할 adapter와 문서를 가리키는 `fix_hint`를 포함합니다.

<!-- section: persistence -->
## 저장과 실행

Resource metadata는 repository port를 통해 접근합니다. Glue는 named volume의 JSON
document를 원자적으로 교체해 저장하고, EMR cluster state는 현재 process-local입니다.
향후 durable adapter를 추가해도 Domain/Application을 변경하지 않도록 port를 유지합니다.
Spark는 shell 없이 명시적 argument vector로 실행하며 bootstrap script는 Proxy가 아닌 EMR
container 경계 안에서만 실행합니다. Python의 원자적 교체는 [os.replace](https://docs.python.org/3/library/os.html#os.replace)를
사용합니다.

<!-- section: non-goals -->
## 비목표

- Glue Job과 JobRun
- Glue Crawler
- 초기 runtime에서 분산 EC2/YARN/HDFS의 물리적 재현
- strict authentication mode가 아닌 경우 IAM policy 평가
- 미문서화된 AWS 버그 재현

<!-- section: sources -->
## 공식 참고 자료

- [AWS Prescriptive Guidance: Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
- [AWS Prescriptive Guidance: 테스트와 CI 모범 사례](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html)
- [AWS SDK endpoint 설정](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
