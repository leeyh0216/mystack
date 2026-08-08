<!-- doc-id: protocols/glue-partition-expressions -->
<!-- lang: en -->

[한국어](glue-partition-expressions.ko.md) | [English](glue-partition-expressions.md)

# Glue partition expressions

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
sequence and `_` for one character. Numeric literals may be signed and decimal. A syntax error
returns modeled `InvalidInputException`; the message reports a position and reason but never logs
the expression value.

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
## Query pipeline and configuration

`PartitionQueries` first resolves the catalog table, then asks the isolated compiler to invoke the
generated ANTLR lexer/parser and map its parse tree to a technology-independent immutable AST once.
The separate typed evaluator applies that AST to repository
results; segment selection follows filtering, and pagination is last. The repository neither
parses expressions nor owns filtering policy.

`glue.partition_expressions.max_length`, `max_tokens`, and `supported_key_types` in the mounted
Mystack YAML control resource bounds and the compatibility profile. The default length matches the
official API model; the token bound is a local denial-of-service guard. Structured events
`glue.partition_expression.parse.*` and `glue.partition_expression.evaluate.*` include only a
short SHA-256 fingerprint, lengths, and counts. If a future boto3, Spark Hive client, or Glue API
change breaks pruning, inspect these events, then update
`glue/grammar/GluePartitionExpression.g4`, the parse-tree adapter, typed evaluator, or YAML policy
independently. `tools/antlr/glue-partition-expression.lock.json` pins the generator URL, version,
digest and timeouts; `make antlr-generate` updates generated sources and `make antlr-check` rejects
drift in CI.

<!-- section: verification -->
## Verification

Fast unit tests cover precedence, every documented operator family, all supported key types,
escaping, invalid syntax/types, and configured limits. A real-port boto3 contract combines typed
filtering with `NextToken` and `Segment`. The CI-only Glue 5 Spark scenario creates a partitioned
Hive table in S3, inserts partitions, and verifies a pruned query through the Glue Hive metastore
client. All test processes use the deadlines in `config/mystack.yaml`.

<!-- section: sources -->
## Official sources

- [AWS Glue GetPartitions API](https://docs.aws.amazon.com/glue/latest/webapi/API_GetPartitions.html)
- [AWS Glue Partition API and ordered values](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog-partitions.html)
- [Using the Glue Data Catalog as the Hive metastore](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html)
- [ANTLR4 getting started guide](https://github.com/antlr/antlr4/blob/4.13.2/doc/getting-started.md)
