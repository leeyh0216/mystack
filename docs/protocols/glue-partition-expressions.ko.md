<!-- doc-id: protocols/glue-partition-expressions -->
<!-- lang: ko -->

[한국어](glue-partition-expressions.ko.md) | [English](glue-partition-expressions.md)

# Glue partition expression

Mystack은 문서화된 `GetPartitions.Expression` 언어를 ANTLR4 `.g4` grammar로 로컬에서
구현합니다. 비교를 위해 AWS에
요청하거나 AWS credential을 사용하지 않습니다. Protocol 기준은 SQL `WHERE`와 유사한 식,
2,048자 제한, 연산자 집합과 지원 partition key type을 정의한 공식
[`GetPartitions` API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)입니다.

<!-- section: grammar -->
## 문법과 우선순위

비교 연산자는 `=`, `==`(SDK client 호환 alias), `<>`, `!=`, `>`, `>=`, `<`, `<=`를 지원합니다.
`IN`, `BETWEEN`, `LIKE`, `IS [NOT] NULL` predicate를 지원하며, 문서화된 `NOT`, `AND`, `OR`,
괄호로 조합할 수 있습니다. 우선순위는 괄호, 단항 `NOT`, predicate, `AND`, `OR` 순입니다.
`NOT IN`, `NOT BETWEEN`, `NOT LIKE`도 직접 사용할 수 있습니다.

Identifier는 일반 이름이나 backtick으로 감싼 이름을 사용합니다. String literal은 작은따옴표와
큰따옴표, `'it''s'`와 같은 delimiter 반복, backslash escape를 지원합니다. `LIKE`의 `%`는 임의
문자열, `_`는 문자 하나를 뜻합니다. 또한 Spark 3.5의 공식
[`HiveShim.convertFilters`](https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala)가
`Contains`, `StartsWith`, `EndsWith`에 생성하는 `.*` wildcard를 인식합니다. 그 밖의 정규식 문법은
일반 문자로 취급합니다. Numeric literal은 부호와 소수를 사용할 수 있습니다. 문법이 잘못되면
modeled `InvalidInputException`을 반환합니다. 메시지에는 위치와 이유만 포함하고 식의 값은 log에
남기지 않습니다.

<!-- section: types -->
## Type 기반 평가

Catalog partition value는 공식 [`Partition` data
type](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)에 따라 순서가
있는 UTF-8 string으로 유지합니다. 비교 전에 저장 값과 literal을 table partition key type으로
함께 변환합니다. `string`, `date`, `timestamp`, `int`, `bigint`, `long`, `tinyint`, `smallint`,
`decimal`을 지원하며 `decimal(precision,scale)` 선언도 포함합니다. Date는 ISO `YYYY-MM-DD`,
timestamp는 끝의 `Z`를 포함한 Python ISO-8601 형식을 받고 timezone이 있으면 UTC로 정규화해
비교합니다.

지원하지 않는 key type, 알 수 없는 key, type으로 변환할 수 없는 값은
`InvalidInputException`을 반환합니다. `LIKE`는 string key에서만 지원합니다. Null 평가는 SQL
3-valued logic을 사용하여 `TRUE`인 row만 반환하고 `IS NULL`/`IS NOT NULL`이 명시적 null
검사입니다. 일반적인 Glue partition에는 key마다 string 하나가 있으므로 null은 주로 손상되거나
migration된 로컬 상태를 보호합니다.

<!-- section: pipeline -->
## 조회 pipeline과 설정

`PartitionQueries`는 먼저 catalog table을 찾은 뒤 격리된 compiler가 생성된 ANTLR
lexer/parser를 호출하고 parse tree를 기술 독립적인 immutable AST로 한 번만 mapping하게 합니다.
별도의 typed evaluator가 이 AST를 repository 조회 결과에
평가하고, 그 다음 segment를 선택하며 pagination을 마지막에 적용합니다. Repository는 expression을
parse하지 않고 filtering 정책도 소유하지 않습니다.

Mount한 Mystack YAML의 `glue.partition_expressions.max_length`, `max_tokens`,
`supported_key_types`로 resource limit과 호환 profile을 제어합니다. 기본 길이는 공식 API model과
같고 token 상한은 로컬 denial-of-service 방어입니다. 구조화 event
`glue.partition_expression.parse.*`, `glue.partition_expression.evaluate.*`,
`glue.partition_expression.segment.*`는 `INFO`에서 기록합니다. 짧은 SHA-256 fingerprint,
연산자만 포함한 AST 형태, key type, segment 좌표, 길이, 개수, 수정 위치 안내만 포함하며 expression
literal과 partition value는 기록하지 않습니다. 이후 boto3, Spark Hive client, Glue API 변경으로
pruning이 깨지면 이 event를 먼저 확인하고 `glue/grammar/GluePartitionExpression.g4`, parse-tree
adapter, typed evaluator, YAML policy를 독립적으로 수정합니다.
`tools/antlr/glue-partition-expression.lock.json`은 generator URL, version, digest, timeout을
고정합니다. `make antlr-generate`로 생성 코드를 갱신하고 CI의 `make antlr-check`가 drift를
차단합니다.

<!-- section: verification -->
## 검증

빠른 unit test는 우선순위, 문서화된 모든 연산자 계열, 지원 key type 전체, escaping, 잘못된
문법/type, 설정 limit을 검증합니다. 실제 port의 boto3 contract는 typed filtering과 `NextToken`,
`Segment`를 함께 검증합니다. CI 전용 Glue 5 Spark 시나리오는 S3에 partitioned Hive table을 만들고
partition을 insert한 뒤 Glue Hive metastore client를 통한 pruning query를 검증합니다. 모든 test
process는 `config/mystack.yaml`의 deadline을 사용합니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [AWS Glue Partition API와 순서가 있는 value](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Glue Data Catalog를 Hive metastore로 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark 3.5.4 Hive metastore filter 변환](https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala)
- [ANTLR4 시작 안내](https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md)
