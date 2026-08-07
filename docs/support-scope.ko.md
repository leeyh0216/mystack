# 지원 범위

한국어 | [English](support-scope.md)

이 문서는 현재 구현과 장기 목표를 구분합니다. “목표”는 현재 빌드가 이미 호환된다는 뜻이 아닙니다.

| 영역 | 현재 상태 | 목표 |
| --- | --- | --- |
| 확장형 Proxy registry | 구현·단위 테스트 완료 | Proxy 코드 변경 없이 새 AWS JSON/SigV4 emulator 등록 |
| AWS JSON 1.1 codec/model 검증 | 구현·단위 테스트 완료 | EMR/Glue modeled request/response/error 처리 |
| LocalStack fallback | 구현·단위 테스트 완료 | EMR/Glue 외 요청의 투명 전달 |
| EMR control plane | 개발 중 | EMR public API 광범위 호환 |
| EMR bootstrap/Spark | 개발 중 | LocalStack S3를 사용하는 실제 Spark 3.5.x local 실행 |
| Glue Data Catalog | 개발 중 | database/table/version/partition/UDF와 문서화된 오류 |
| Spark + Hive + Glue Catalog | 개발 중 | Hive 호환 metadata 상호운용 |
| Spark + Iceberg + Glue Catalog | 개발 중 | LocalStack S3에서 Iceberg 1.7.1 read/write |
| Web console | 계획 | EMR 및 Glue Catalog 리소스/상태/로그 조회 |

## 명시적 제외

- AWS Glue Job과 JobRun API
- AWS Glue Crawler
- 미문서화된 AWS 버그 재현
- 기본 local mode의 production IAM authorization 의미론
- EC2/YARN/HDFS 물리적 분산 환경 재현

## 버전 기준선

- Python API 서비스: Python 3.11, CI에서 3.11/3.12 검증
- Protocol model: botocore 1.43.66, `contracts/service-model-manifest.json`에서 추적
- Spark: 3.5.x, Glue 상호운용 profile은 Spark 3.5.4
- Java: 17
- Iceberg: Glue 5.0 profile 기준 1.7.1

Glue 버전은 [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)와 [공식 Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html), EMR 의미론은 [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html)를 기준으로 합니다.

