<!-- doc-id: protocols/glue-partition-expressions -->
<!-- lang: ko -->

[한국어](glue-partition-expressions.ko.md) | [English](glue-partition-expressions.md)

# Glue partition expression

<!-- toc:start -->
## 목차

- [문법과 우선순위](#문법과-우선순위)
- [Type 기반 평가](#type-기반-평가)
- [조회 pipeline, SQLite pushdown과 설정](#조회-pipeline-sqlite-pushdown과-설정)
- [검증](#검증)
- [공식 출처](#공식-출처)
<!-- toc:end -->

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
## 조회 pipeline, SQLite pushdown과 설정

`PartitionQueries`는 parent table을 찾기 전에 structural `NextToken`, segment 범위, ANTLR 문법을
검증합니다. 그 뒤 해석된 partition key schema에 AST를 bind합니다. Repository는 expression text를
parse하지 않습니다. 이미 bind된 immutable AST만 받아 지원 node를 parameterized SQLite predicate로
compile합니다. field alias는 검증된 key ordinal에서만 만들고 literal, cursor position, segment 좌표는
모두 DB-API parameter로 전달합니다.

```text
NextToken shape -> Segment -> ANTLR parse -> table lookup -> schema bind
    -> stable evaluator 1건 probe -> typed SQLite predicate + segment join
    -> ORDER BY (order_key, partition_id) -> LIMIT MaxResults + 1
```

첫 probe는 evaluator의 lazy literal conversion과 오류 순서를 유지합니다. 따라서 빈 table은 실제로
사용되지 않는 잘못된 literal을 오류로 바꾸지 않습니다. Typed projection fact는 모든 partition을
메모리에 올리지 않고 뒤쪽 row의 잘못된 value도 감지합니다. Application은 이 neutral fact를
`InvalidInputException`으로 mapping하며, raw partition value나 SQL 문은 log에 남기지 않습니다.

SQLite는 안정적인 binary order key와 total별 persisted segment assignment를 저장합니다. Opaque
continuation token에는 version, request-context fingerprint, surrogate row ID만 있고 이름이나 partition
value는 없습니다. 다른 catalog/table/expression/segment의 token은 거부됩니다. 일반
`GetPartitions`는 total-count query를 실행하지 않습니다. 참조 key 검증은 index된 중립 health fact를
읽으므로 invalid value가 없다는 이유만으로 모든 partition을 탐색하지 않습니다. 결과 materialization은
요청 page와 lookahead로 제한됩니다. 현재 ANTLR grammar는 모두 SQL/UDF로 compile합니다. evaluator가
지원하지만 정확한 SQLite compiler가 아직 없는 이후 node는 `ORDER BY (order_key, partition_id)` seek
streaming으로 최대 `fallback_max_candidates` row만 평가하며 catalog 목록을 snapshot하지 않습니다. cap을
넘으면 값과 식을 노출하지 않는 narrowing hint가 포함된 결정적 `InvalidInputException`을 반환합니다.
fallback의 strategy는 `sqlite-keyset-bounded-evaluator`이며, 이후 node는 이 상한 검증 범위를
갖춘 뒤에만 지원 범위에 포함할 수 있습니다.

Mount한 Mystack YAML의 `glue.partition_expressions.max_length`, `max_tokens`,
`fallback_max_candidates`, `supported_key_types`로 resource limit과 호환 profile을 제어합니다. 기본 길이는 공식 API model과
같고 token 상한은 로컬 denial-of-service 방어입니다. 구조화 event
`glue.partition_expression.parse.*`, `glue.partition_expression.bind.*`,
`glue.partition_query.plan.*`, `glue.partition_query.preflight.failed`,
`glue.partition_query.fallback`,
`glue.sqlite_catalog.query.page.after`는 `INFO`에서 기록합니다. expression fingerprint,
연산자만 포함한 AST 형태, key type, segment 좌표, 요청/반환 page 개수, strategy, duration, 수정 위치
안내만 포함하며 literal, token, partition value, SQL text는 기록하지 않습니다. 이후 boto3, Spark Hive
client, Glue API 변경으로 pruning이 깨지면 이 event를 먼저 확인하고
`glue/grammar/GluePartitionExpression.g4`, parse-tree adapter/evaluator, 격리된 SQLite
compiler/projection module을 수정합니다. `tools/antlr/glue-partition-expression.lock.json`은 generator
URL, version, digest, timeout을 고정합니다. `make antlr-generate`로 생성 코드를 갱신하고 CI의
`make antlr-check`가 drift를 차단합니다.

<!-- section: verification -->
## 검증

빠른 unit test는 SQLite result page와 evaluator를 비교하고, keyset continuation, token scope, order,
typed projection, `LIKE`, segment union/disjointness, 오류 순서를 검증합니다. 실제 port의 boto3
contract는 typed filtering과 `NextToken`, `Segment`를 함께 검증합니다. CI 전용 Glue 5 Spark
시나리오는 S3에 partitioned Hive table을 만들고 partition을 insert한 뒤 Glue Hive metastore client를
통한 pruning query를 검증합니다. 모든 test process는 `config/mystack.yaml`의 deadline을 사용합니다.

<!-- section: sources -->
## 공식 출처

- [AWS Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [AWS Glue Partition API와 순서가 있는 value](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Glue Data Catalog를 Hive metastore로 사용](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark 3.5.4 Hive metastore filter 변환](https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala)
- [ANTLR4 시작 안내](https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md)
- [SQLite query planner](https://www.sqlite.org/queryplanner.html)
- [SQLite query planner](https://www.sqlite.org/queryplanner.html)
- [SQLite expression syntax](https://www.sqlite.org/lang_expr.html)
- [SQLite application-defined function](https://www.sqlite.org/appfunc.html)
