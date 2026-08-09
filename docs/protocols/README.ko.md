<!-- doc-id: protocols-index -->
<!-- lang: ko -->

[한국어](README.ko.md) | [English](README.md)

# Protocol 구현 안내

<!-- toc:start -->
## 목차

- [주제별 읽는 순서](#주제별-읽는-순서)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: overview -->
이 문서는 공개 AWS 호환 API를 뒷받침하는 내부 동작을 설명합니다. 기여자는 service 안내에서 시작한 뒤
변경하려는 경로를 순서대로 읽습니다.

<!-- section: reading-order -->
## 주제별 읽는 순서

### Glue Data Catalog

[Glue 프로토콜 안내](glue/README.ko.md)부터 읽고 필요한 경로를 선택합니다:
[Catalog](glue/catalog.ko.md), [Hive](glue/hive.ko.md), [Iceberg](glue/iceberg.ko.md).

### Amazon EMR

1. [Startup cluster](emr/emr-startup-clusters.ko.md)
2. [Pre-start action](emr/emr-prestart.ko.md)
3. [Log layout](emr/emr-log-layout.ko.md)

### 공유 wire protocol

- [AWS JSON 1.1](aws-json/aws-json-1.1.ko.md)

문서에서 CI 전용 workload를 언급하면 runtime 기능이 아니라 test infrastructure입니다. 해당 source와
scenario 이름은 대응하는 `tests/e2e` case와 함께 변경합니다.

<!-- section: sources -->
## 공식 참고 자료

- [AWS JSON protocol reference](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.LowLevelAPI.html)
- [Apache Iceberg documentation](https://iceberg.apache.org/docs/latest/)
