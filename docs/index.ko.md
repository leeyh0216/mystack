<!-- doc-id: docs-index -->
<!-- lang: ko -->

[한국어](index.ko.md) | [English](index.md)

# 사용자 안내

이 문서의 기본 독자는 Mystack을 사용해 애플리케이션과 데이터 파이프라인을 개발하는 분입니다.
저장소 구현, 프로토콜, CI와 배포를 관리하는 분은 [유지보수 안내](maintainers.ko.md)로
이동하세요.

<!-- section: start -->
## 처음 시작하기

1. [상세 사용 안내](getting-started.ko.md)로 Docker Compose를 시작하고 공개 endpoint를 확인합니다.
2. [설정 안내](configuration.ko.md)에서 port, 제한 시간, data path와 file override를 선택합니다.
3. [지원 범위](support-scope.ko.md)와 [Client 호환성 표](compatibility/client-matrix.ko.md)에서
   사용하려는 API와 라이브러리의 실제 검증 범위를 확인합니다.

<!-- section: clients -->
## Client별 경로

| Client 또는 사용 목적 | 현재 검증 | 시작 문서 |
| --- | --- | --- |
| AWS CLI와 boto3 | 같은 공개 Proxy에서 EMR 13개, Glue 22개 operation | [상세 사용 안내](getting-started.ko.md) |
| AWS SDK for pandas 3.17.0 | Partitioned Parquet S3 write/read와 Glue table/partition | [상세 사용 안내](getting-started.ko.md) |
| Spark 3.5.4 Glue Hive client | Complex type Parquet create/insert/read | [Client 호환성 표](compatibility/client-matrix.ko.md) |
| Apache Iceberg 1.7.1 GlueCatalog | Namespace/table create, append, read, schema evolution | [Client 호환성 표](compatibility/client-matrix.ko.md) |
| EMR Spark step | S3 bootstrap, Python/JAR local Spark, S3A output, cancel | [지원 범위](support-scope.ko.md) |

표에 없는 라이브러리나 함수는 자동으로 지원되는 것으로 간주하지 않습니다. 고정 botocore model의
operation별 구현 상태는 [API coverage](compatibility/api-coverage.ko.md)에 있습니다.

<!-- section: operate -->
## 사용 중 설정과 진단

- YAML, environment override, Docker mount: [설정 안내](configuration.ko.md)
- Resource, EMR log, route, thread/task UI: [관리 Console 안내](console.ko.md)
- 구조화 log와 관리 endpoint: [관찰성 안내](observability.ko.md)
- Glue 일부 동작 교체와 extension wheel: [Glue 확장 SPI 안내](extensions.ko.md)

<!-- section: limits -->
## 먼저 알아야 할 제한

Glue Job, JobRun, Crawler와 Athena query 실행은 현재 범위가 아닙니다. Spark/Iceberg와 AWS
SDK for pandas도 호환성 표에 적힌 경로만 검증했습니다. Production IAM, EC2/YARN/HDFS 분산
환경과 미문서화된 AWS 결함을 재현하지 않습니다.

<!-- section: maintainers -->
## 저장소를 변경하는 경우

개발 환경, 아키텍처, 프로토콜 분석, 시험, CI, 배포, 상위 의존성 변경 대응은
[유지보수 안내](maintainers.ko.md)에만 분류합니다. 사용자에게 필요한 문서는 이 안내에 먼저
연결하고, 구현 상세는 유지보수 안내로 보냅니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS SDK endpoint 구성](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- [Amazon EMR API](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)
- [AWS Glue API](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
- [Docker Compose](https://docs.docker.com/reference/compose-file/)
