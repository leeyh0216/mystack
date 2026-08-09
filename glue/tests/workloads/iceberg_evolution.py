"""Table-driven Iceberg partition, schema, sort, and identifier evolution scenario.

References:
- https://iceberg.apache.org/docs/1.7.1/partitioning/
- https://iceberg.apache.org/docs/1.7.1/evolution/
- https://iceberg.apache.org/docs/1.7.1/spark-ddl/
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pyspark.sql import SparkSession


@dataclass(frozen=True, slots=True)
class IcebergEvolutionScenario:
    name: str
    statement: str


def exercise_iceberg_evolution(
    spark: SparkSession,
    *,
    catalog_name: str,
    database: str,
) -> dict[str, object]:
    """Commit every reviewed evolution form through Spark GlueCatalog."""

    table = "iceberg_evolution"
    qualified = f"{catalog_name}.`{database}`.`{table}`"
    _run(
        spark,
        (
            IcebergEvolutionScenario(
                "create-iceberg-evolution-table",
                f"""
                CREATE TABLE {qualified} (
                    id BIGINT NOT NULL,
                    category STRING,
                    metric INT,
                    ratio FLOAT,
                    amount DECIMAL(9, 2),
                    ts TIMESTAMP,
                    event STRUCT<kind:STRING,details:STRUCT<code:INT>>,
                    obsolete STRING
                ) USING iceberg
                TBLPROPERTIES ('format-version'='2')
                """,
            ),
            IcebergEvolutionScenario(
                "insert-before-evolution",
                f"""
                INSERT INTO {qualified} VALUES (
                    1, 'alpha', 10, CAST(1.5 AS FLOAT), CAST(12.34 AS DECIMAL(9, 2)),
                    TIMESTAMP'2026-01-01 10:15:00',
                    NAMED_STRUCT('kind', 'created', 'details', NAMED_STRUCT('code', 100)),
                    'remove-me'
                )
                """,
            ),
        ),
    )
    _run(spark, _partition_evolution(qualified))
    _run(spark, _schema_evolution(qualified))
    _run(spark, _sort_and_identifier_evolution(qualified))
    _run(
        spark,
        (
            IcebergEvolutionScenario(
                "insert-after-evolution",
                f"""
                INSERT INTO {qualified} (
                    id, category_name, metric, ratio, amount, ts, event, note
                ) SELECT
                    CAST(2 AS BIGINT), 'beta', CAST(20 AS BIGINT), CAST(2.5 AS DOUBLE),
                    CAST(98.76 AS DECIMAL(12, 2)), TIMESTAMP'2026-02-02 11:30:00',
                    NAMED_STRUCT(
                        'kind', 'updated',
                        'details', NAMED_STRUCT('status_code', 200, 'message', 'accepted')
                    ),
                    'after'
                """,
            ),
        ),
    )

    frame = spark.table(qualified)
    filtered_count = frame.where(
        "category_name = 'beta' "
        "AND ts >= TIMESTAMP'2026-02-02 00:00:00' "
        "AND ts < TIMESTAMP'2026-02-03 00:00:00'"
    ).count()
    return {
        "iceberg_evolution_table": table,
        "iceberg_evolution_count": frame.count(),
        "iceberg_evolution_filtered_count": filtered_count,
        "iceberg_evolution_columns": frame.columns,
    }


def _partition_evolution(qualified: str) -> tuple[IcebergEvolutionScenario, ...]:
    """Cover every transform and add/drop/replace from the Iceberg 1.7.1 Spark DDL."""

    return (
        IcebergEvolutionScenario(
            "add-identity-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD category AS category_identity",
        ),
        IcebergEvolutionScenario(
            "add-bucket-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD bucket(8, id) AS id_bucket",
        ),
        IcebergEvolutionScenario(
            "add-truncate-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD truncate(3, category) AS category_trunc",
        ),
        IcebergEvolutionScenario(
            "add-year-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD year(ts) AS ts_year",
        ),
        IcebergEvolutionScenario(
            "add-month-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD month(ts) AS ts_month",
        ),
        IcebergEvolutionScenario(
            "add-day-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD day(ts) AS ts_day",
        ),
        IcebergEvolutionScenario(
            "add-hour-partition",
            f"ALTER TABLE {qualified} ADD PARTITION FIELD hour(ts) AS ts_hour",
        ),
        IcebergEvolutionScenario(
            "replace-hour-partition",
            (
                f"ALTER TABLE {qualified} REPLACE PARTITION FIELD ts_hour "
                "WITH bucket(16, id) AS id_shard"
            ),
        ),
        IcebergEvolutionScenario(
            "drop-identity-partition",
            f"ALTER TABLE {qualified} DROP PARTITION FIELD category_identity",
        ),
    )


def _schema_evolution(qualified: str) -> tuple[IcebergEvolutionScenario, ...]:
    return (
        IcebergEvolutionScenario(
            "add-top-level-column",
            f"ALTER TABLE {qualified} ADD COLUMN note STRING",
        ),
        IcebergEvolutionScenario(
            "add-nested-column",
            f"ALTER TABLE {qualified} ADD COLUMN event.details.message STRING",
        ),
        IcebergEvolutionScenario(
            "add-nested-temporary-column",
            f"ALTER TABLE {qualified} ADD COLUMN event.details.temporary STRING",
        ),
        IcebergEvolutionScenario(
            "rename-top-level-column",
            f"ALTER TABLE {qualified} RENAME COLUMN category TO category_name",
        ),
        IcebergEvolutionScenario(
            "rename-nested-column",
            f"ALTER TABLE {qualified} RENAME COLUMN event.details.code TO status_code",
        ),
        IcebergEvolutionScenario(
            "widen-int-column",
            f"ALTER TABLE {qualified} ALTER COLUMN metric TYPE BIGINT",
        ),
        IcebergEvolutionScenario(
            "widen-float-column",
            f"ALTER TABLE {qualified} ALTER COLUMN ratio TYPE DOUBLE",
        ),
        IcebergEvolutionScenario(
            "widen-decimal-column",
            f"ALTER TABLE {qualified} ALTER COLUMN amount TYPE DECIMAL(12, 2)",
        ),
        IcebergEvolutionScenario(
            "drop-top-level-column",
            f"ALTER TABLE {qualified} DROP COLUMN obsolete",
        ),
        IcebergEvolutionScenario(
            "drop-nested-column",
            f"ALTER TABLE {qualified} DROP COLUMN event.details.temporary",
        ),
    )


def _sort_and_identifier_evolution(
    qualified: str,
) -> tuple[IcebergEvolutionScenario, ...]:
    return (
        IcebergEvolutionScenario(
            "set-sort-order",
            (
                f"ALTER TABLE {qualified} WRITE ORDERED BY "
                "category_name ASC NULLS LAST, id DESC NULLS FIRST"
            ),
        ),
        IcebergEvolutionScenario(
            "unset-sort-order",
            f"ALTER TABLE {qualified} WRITE UNORDERED",
        ),
        IcebergEvolutionScenario(
            "replace-sort-order",
            (
                f"ALTER TABLE {qualified} WRITE ORDERED BY "
                "category_name ASC NULLS LAST, id DESC NULLS FIRST"
            ),
        ),
        IcebergEvolutionScenario(
            "set-identifier-field",
            f"ALTER TABLE {qualified} SET IDENTIFIER FIELDS id",
        ),
        IcebergEvolutionScenario(
            "drop-identifier-field",
            f"ALTER TABLE {qualified} DROP IDENTIFIER FIELDS id",
        ),
        IcebergEvolutionScenario(
            "replace-identifier-field",
            f"ALTER TABLE {qualified} SET IDENTIFIER FIELDS id",
        ),
    )


def _run(spark: SparkSession, scenarios: tuple[IcebergEvolutionScenario, ...]) -> None:
    for scenario in scenarios:
        print(
            "MYSTACK_E2E_SCENARIO="
            + json.dumps({"name": scenario.name, "phase": "before"}, sort_keys=True)
        )
        spark.sql(scenario.statement).collect()
        print(
            "MYSTACK_E2E_SCENARIO="
            + json.dumps({"name": scenario.name, "phase": "after"}, sort_keys=True)
        )
