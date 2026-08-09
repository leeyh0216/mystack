<!-- doc-id: protocols/glue/glue-partition-expressions -->
<!-- lang: en -->

[한국어](glue-partition-expressions.ko.md) | [English](glue-partition-expressions.md)

# Glue partition expressions

<!-- toc:start -->
## Contents

- [Grammar and precedence](#grammar-and-precedence)
- [Typed evaluation](#typed-evaluation)
- [Query pipeline, SQLite pushdown, and configuration](#query-pipeline-sqlite-pushdown-and-configuration)
- [Verification](#verification)
- [Official sources](#official-sources)
<!-- toc:end -->

Mystack implements the documented `GetPartitions.Expression` language locally with an ANTLR4
`.g4` grammar. It does not send
requests to AWS or use AWS credentials for comparison. The protocol source is the official
[`GetPartitions` API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html), which
defines a SQL `WHERE`-like expression, a 2,048-character limit, the operator set, and supported
partition-key types.

<!-- section: grammar -->
## Grammar and precedence

Supported comparisons are `=`, `==` (SDK-client compatibility alias), `<>`, `!=`, `>`, `>=`, `<`,
and `<=`. Predicates include `IN`, `BETWEEN`, `LIKE`, and `IS [NOT] NULL`; each supports the
documented logical composition through `NOT`, `AND`, `OR`, and parentheses. Precedence is
parentheses, unary `NOT`, predicates, `AND`, then `OR`. `NOT IN`, `NOT BETWEEN`, and `NOT LIKE` are
accepted directly.

Identifiers may be unquoted names or backtick-quoted names. String literals accept single or
double quotes, doubled delimiters such as `'it''s'`, and backslash escaping. `LIKE` uses `%` for any
sequence and `_` for one character. It also recognizes the `.*` wildcard emitted for `Contains`,
`StartsWith`, and `EndsWith` by Spark 3.5's official
[`HiveShim.convertFilters`](https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala).
Other regular-expression syntax remains literal. Numeric literals may be signed and decimal. A
syntax error returns modeled `InvalidInputException`; the message reports a position and reason but
never logs the expression value.

<!-- section: types -->
## Typed evaluation

Catalog partition values remain ordered UTF-8 strings as specified by the official
[`Partition` data type](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html).
Before comparison, Mystack converts both the stored value and literal according to the table's
partition-key type. Supported families are `string`, `date`, `timestamp`, `int`, `bigint`, `long`,
`tinyint`, `smallint`, and `decimal`, including `decimal(precision,scale)` declarations. Dates use
ISO `YYYY-MM-DD`; timestamps accept Python ISO-8601 forms, including a trailing `Z`, and normalize
timezone-aware values to UTC for comparison.

Invalid key types, unknown keys, and values that cannot be converted return
`InvalidInputException`. `LIKE` is limited to string keys. Null evaluation follows SQL
three-valued logic: only `TRUE` rows are returned, and `IS NULL`/`IS NOT NULL` are the explicit null
tests. Glue partitions normally contain one string per key, so null primarily protects malformed
or migrated local state.

<!-- section: pipeline -->
## Query pipeline, SQLite pushdown, and configuration

`PartitionQueries` validates a structural `NextToken`, segment bounds, and ANTLR syntax before it
looks up the parent table. It then binds the AST to the resolved partition-key schema. The
repository never parses expression text: it receives only this bound immutable AST and compiles
the supported nodes to parameterized SQLite predicates. Field aliases come only from validated key
ordinals; literals, cursor positions, and segment coordinates are DB-API parameters.

```text
NextToken shape -> Segment -> ANTLR parse -> table lookup -> schema bind
    -> one stable evaluator probe -> typed SQLite predicate + segment join
    -> ORDER BY (order_key, partition_id) -> LIMIT MaxResults + 1
```

The first probe preserves the evaluator's established lazy literal-conversion and error order: an
empty table does not turn an otherwise unused invalid literal into an error. Typed projection facts
also detect a malformed value in a later row without loading every partition. The application maps
that neutral fact to `InvalidInputException`; neither a raw partition value nor a SQL statement is
written to logs.

SQLite stores a stable binary order key and per-total persisted segment assignments. The opaque
continuation token contains only a version, a request-context fingerprint, and a surrogate row ID;
it contains no names or partition values. A token from another catalog/table/expression/segment is
rejected. Ordinary `GetPartitions` does not issue a total-count query. Referenced-key validation
reads durable, neutral health facts by index; it does not search every partition merely because no
invalid value exists. Result materialization remains bounded to the requested page plus its lookahead.
The current ANTLR grammar is fully compiled to SQL/UDFs. If a future evaluator-supported node has
no exact SQLite compiler yet, the repository uses `ORDER BY (order_key, partition_id)` seek
streaming and evaluates at most `fallback_max_candidates` rows; it never snapshots a catalog list.
Crossing that cap returns a deterministic `InvalidInputException` with a safe narrowing hint. The
fallback emits `sqlite-keyset-bounded-evaluator`; it contains neither the expression nor a stored
value. A future node needs this bounded differential coverage before it is advertised as supported.

`glue.partition_expressions.max_length`, `max_tokens`, `fallback_max_candidates`, and `supported_key_types` in the mounted
Mystack YAML control resource bounds and the compatibility profile. The default length matches the
official API model; the token bound is a local denial-of-service guard. Structured events
`glue.partition_expression.parse.*`, `glue.partition_expression.bind.*`,
`glue.partition_query.plan.*`, `glue.partition_query.preflight.failed`,
`glue.partition_query.fallback`, and
`glue.sqlite_catalog.query.page.after` are emitted at `INFO`. They include only an expression
fingerprint, operator-only shape, key types, segment coordinates, requested/returned page counts,
strategy, duration, and a targeted fix hint. They never include literals, tokens, partition values,
or SQL text. If a future boto3, Spark Hive client, or Glue API change breaks pruning, inspect these
events, then update `glue/grammar/GluePartitionExpression.g4`, the parse-tree adapter/evaluator, or
the isolated SQLite compiler/projection module. `tools/antlr/glue-partition-expression.lock.json`
pins the generator URL, version, digest and timeouts; `make antlr-generate` updates generated
sources and `make antlr-check` rejects drift in CI.

<!-- section: verification -->
## Verification

Fast unit tests compare SQLite result pages with the evaluator, cover keyset continuation, token
scope, ordering, typed projections, `LIKE`, segment union/disjointness, and error precedence. A
real-port boto3 contract combines typed filtering with `NextToken` and `Segment`. The CI-only Glue
5 Spark scenario creates a partitioned Hive table in S3, inserts partitions, and verifies a pruned
query through the Glue Hive metastore client. All test processes use the deadlines in
`config/mystack.yaml`.

<!-- section: sources -->
## Official sources

- [AWS Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [AWS Glue Partition API and ordered values](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Using the Glue Data Catalog as the Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [Spark 3.5.4 Hive metastore filter conversion](https://github.com/apache/spark/blob/v3.5.4/sql/hive/src/main/scala/org/apache/spark/sql/hive/client/HiveShim.scala)
- [ANTLR4 getting started guide](https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md)
- [SQLite query planner](https://www.sqlite.org/queryplanner.html)
- [SQLite expression syntax](https://www.sqlite.org/lang_expr.html)
- [SQLite application-defined functions](https://www.sqlite.org/appfunc.html)
