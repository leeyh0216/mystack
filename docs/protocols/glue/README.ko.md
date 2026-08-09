<!-- doc-id: glue-protocol-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# Glue 프로토콜 안내

<!-- toc:start -->
## 목차

- [주제 선택](#주제-선택)
- [변경 점검표](#변경-점검표)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
Glue 호환 카탈로그 서비스를 수정하는 기여자의 시작점입니다. 바꾸려는 동작에 맞는 주제를 고르면,
각 안내가 상세 설계 문서의 읽는 순서와 연결된 테스트 경계를 제공합니다.

<!-- section: topic -->
## 주제 선택

| 변경 대상 | 먼저 읽을 안내 | Test 경계 |
| --- | --- | --- |
| Catalog persistence, database/table 동작, 모델 오류, partition | [Catalog](catalog.ko.md) | `glue/tests/` boto3 계약 |
| Spark SQL Hive metastore discovery, partition DDL, repair, ALTER TABLE 메타데이터 | [Hive](hive.ko.md) | `tests/e2e/test_glue_spark_catalog.py` |
| Iceberg GlueCatalog 메타데이터, commit, evolution, DML, ref, lifecycle, optimizer | [Iceberg](iceberg.ko.md) | `tests/e2e/test_glue_spark_catalog.py` |

<!-- section: checklist -->
## 변경 점검표

1. 가장 작은 서비스 component와 black-box 또는 E2E 테스트를 함께 변경합니다.
2. 동작이나 제외 범위가 바뀌면 해당 주제 문서를 갱신합니다.
3. `make compatibility-check`를 실행하고 실행 환경 변경에는 관련 Compose 클라이언트 lab도 실행합니다.
4. Glue Job, JobRun, Crawler, IAM, Lake Formation은 명시적인 범위 제외입니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS Glue API Reference](https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html)
