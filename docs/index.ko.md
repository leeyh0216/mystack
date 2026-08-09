<!-- doc-id: docs-index -->
<!-- lang: ko -->

[한국어](index.ko.md) | [English](index.md)

# Mystack 문서

<!-- toc:start -->
## 목차

- [개요](#개요)
- [시작하기](#시작하기)
- [Glue Data Catalog](#glue-data-catalog)
- [Amazon EMR](#amazon-emr)
- [설정과 운영](#설정과-운영)
- [Contributors](#contributors)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

이 문서는 애플리케이션 또는 데이터 파이프라인 개발자가 Mystack 문서를 탐색하는 출발점입니다.
각 문서는 답하려는 작업부터 설명하고, 필요한 경우에만 더 깊은 기술 문서로 연결합니다.

<!-- section: overview -->
## 개요

Mystack은 Amazon EMR, AWS Glue Data Catalog, Spark, LocalStack S3를 위한 로컬 개발 환경을
제공합니다. Docker Compose를 시작한 뒤 실행하려는 작업에 따라 Glue 또는 EMR 문서를 선택합니다.

<!-- section: start -->
## 시작하기

- [Docker Compose 시작과 AWS CLI 또는 boto3 설정](getting-started.ko.md)
- [게시 image 배포 변경](configuration.ko.md)
- [관리 UI와 진단 사용](operations.ko.md)

<!-- section: glue -->
## Glue Data Catalog

- [boto3, AWS SDK for pandas, Spark Hive, Iceberg로 Glue 사용](glue.ko.md)
- [Client 선택과 Glue/EMR 요청 경로 따라가기](client-workflows.ko.md)
- [Client와 library 호환성 확인](compatibility/client-matrix.ko.md)
- [사용자 관점 지원 범위 확인](support-scope.ko.md)
- [Glue SQLite catalog, 검증한 runtime, durability 정책 운영](protocols/glue/glue-sqlite-runtime.ko.md)

<!-- section: emr -->
## Amazon EMR

- [Cluster 생성과 Spark 또는 PySpark Step 제출](emr.ko.md)
- [Step log와 LogUri object 찾기](protocols/emr/emr-log-layout.ko.md)
- [신뢰한 image pre-start action 설정](protocols/emr/emr-prestart.ko.md)
- [Container 시작 시 cluster 미리 구성](protocols/emr/emr-startup-clusters.ko.md)

<!-- section: operations -->
## 설정과 운영

- [설정 reference](configuration.ko.md)
- [관리 UI, live log, 진단](operations.ko.md)
- [구조화 log와 문제 해결](observability.ko.md)

<!-- section: contributors -->
## Contributors

구현, protocol, architecture, 개발 환경, test, CI, release 문서는
[Contributors 안내](maintainers.ko.md)에서 시작합니다. 사용자 지원 안내와 분리된 전체 AWS
API/endpoint 인벤토리는 [API 호환성 reference](compatibility/api-coverage.ko.md)에 있습니다.

<!-- section: sources -->
## 공식 참고 자료

- [Amazon EMR 문서](https://docs.aws.amazon.com/emr/)
- [AWS Glue 문서](https://docs.aws.amazon.com/glue/)
- [Docker Compose reference](https://docs.docker.com/reference/compose-file/)
