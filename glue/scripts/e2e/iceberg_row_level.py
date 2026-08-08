"""Table-driven Iceberg v2 row-level write scenario for the pinned Glue profile.

References:
- https://iceberg.apache.org/docs/1.7.1/spark-writes/
- https://iceberg.apache.org/docs/1.7.1/configuration/
- https://iceberg.apache.org/spec/#snapshots
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pyspark.sql import SparkSession


@dataclass(frozen=True, slots=True)
class IcebergRowLevelScenario:
    name: str
    statement: str


@dataclass(frozen=True, slots=True)
class IcebergRowLevelTable:
    table: str
    qualified: str
    write_mode: str


def exercise_iceberg_row_level_writes(
    spark: SparkSession,
    *,
    catalog_name: str,
    database: str,
) -> dict[str, object]:
    """Exercise COW and MOR through Iceberg; Mystack only commits catalog pointers."""

    copy_on_write = _table(catalog_name, database, "iceberg_row_cow", "copy-on-write")
    merge_on_read = _table(catalog_name, database, "iceberg_row_mor", "merge-on-read")
    _create(spark, copy_on_write)
    _create(spark, merge_on_read)

    _run(
        spark,
        (
            IcebergRowLevelScenario(
                "cow-insert-initial",
                f"""
                INSERT INTO {copy_on_write.qualified} VALUES
                  (1, 'north', 10),
                  (2, 'north', 20),
                  (3, 'south', 30)
                """,
            ),
            IcebergRowLevelScenario(
                "cow-insert-append",
                f"INSERT INTO {copy_on_write.qualified} VALUES (4, 'south', 40)",
            ),
        ),
    )
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    _run(
        spark,
        (
            IcebergRowLevelScenario(
                "cow-dynamic-insert-overwrite",
                f"""
                INSERT OVERWRITE {copy_on_write.qualified}
                SELECT * FROM VALUES
                  (CAST(1 AS BIGINT), 'north', 11),
                  (CAST(5 AS BIGINT), 'north', 50)
                AS replacement(id, category, amount)
                """,
            ),
        ),
    )
    copy_on_write_after_overwrite = _rows(spark, copy_on_write.qualified)
    _run(
        spark,
        (
            IcebergRowLevelScenario(
                "cow-update",
                f"UPDATE {copy_on_write.qualified} SET amount = 31 WHERE id = 3",
            ),
            IcebergRowLevelScenario(
                "cow-delete",
                f"DELETE FROM {copy_on_write.qualified} WHERE id = 4",
            ),
            IcebergRowLevelScenario(
                "cow-merge",
                _merge_statement(
                    copy_on_write.qualified,
                    matched_id=1,
                    matched_category="north",
                    update_amount=111,
                    delete_id=5,
                    insert_id=6,
                    insert_category="south",
                    insert_amount=60,
                ),
            ),
        ),
    )
    invalid_merge_error = _expect_failure(
        spark,
        IcebergRowLevelScenario(
            "cow-invalid-multiple-source-match",
            f"""
            MERGE INTO {copy_on_write.qualified} AS target
            USING (
              SELECT * FROM VALUES
                (CAST(1 AS BIGINT), 999),
                (CAST(1 AS BIGINT), 888)
              AS duplicate_source(id, amount)
            ) AS source
            ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET amount = source.amount
            """,
        ),
    )

    _run(
        spark,
        (
            IcebergRowLevelScenario(
                "mor-insert-initial",
                f"""
                INSERT INTO {merge_on_read.qualified} VALUES
                  (10, 'north', 100),
                  (11, 'north', 110),
                  (12, 'south', 120),
                  (14, 'north', 140)
                """,
            ),
            IcebergRowLevelScenario(
                "mor-update",
                f"UPDATE {merge_on_read.qualified} SET amount = 101 WHERE id = 10",
            ),
            IcebergRowLevelScenario(
                "mor-delete",
                f"DELETE FROM {merge_on_read.qualified} WHERE id = 11",
            ),
            IcebergRowLevelScenario(
                "mor-merge",
                _merge_statement(
                    merge_on_read.qualified,
                    matched_id=12,
                    matched_category="south",
                    update_amount=121,
                    delete_id=14,
                    insert_id=13,
                    insert_category="south",
                    insert_amount=130,
                ),
            ),
        ),
    )

    return {
        "iceberg_row_cow_table": copy_on_write.table,
        "iceberg_row_cow_after_overwrite": copy_on_write_after_overwrite,
        "iceberg_row_cow_final": _rows(spark, copy_on_write.qualified),
        "iceberg_row_cow_invalid_merge_error": invalid_merge_error,
        "iceberg_row_mor_table": merge_on_read.table,
        "iceberg_row_mor_final": _rows(spark, merge_on_read.qualified),
    }


def _table(
    catalog_name: str,
    database: str,
    table: str,
    write_mode: str,
) -> IcebergRowLevelTable:
    return IcebergRowLevelTable(
        table=table,
        qualified=f"{catalog_name}.`{database}`.`{table}`",
        write_mode=write_mode,
    )


def _create(spark: SparkSession, table: IcebergRowLevelTable) -> None:
    _run(
        spark,
        (
            IcebergRowLevelScenario(
                f"create-{table.table}",
                f"""
                CREATE TABLE {table.qualified} (
                    id BIGINT,
                    category STRING,
                    amount INT
                ) USING iceberg
                PARTITIONED BY (category)
                TBLPROPERTIES (
                    'format-version'='2',
                    'write.delete.mode'='{table.write_mode}',
                    'write.update.mode'='{table.write_mode}',
                    'write.merge.mode'='{table.write_mode}'
                )
                """,
            ),
        ),
    )


def _merge_statement(
    qualified: str,
    *,
    matched_id: int,
    matched_category: str,
    update_amount: int,
    delete_id: int,
    insert_id: int,
    insert_category: str,
    insert_amount: int,
) -> str:
    return f"""
        MERGE INTO {qualified} AS target
        USING (
          SELECT * FROM VALUES
            (CAST({matched_id} AS BIGINT), '{matched_category}', {update_amount}, 'update'),
            (CAST({delete_id} AS BIGINT), 'north', 0, 'delete'),
            (CAST({insert_id} AS BIGINT), '{insert_category}', {insert_amount}, 'insert')
          AS changes(id, category, amount, operation)
        ) AS source
        ON target.id = source.id
        WHEN MATCHED AND source.operation = 'delete' THEN DELETE
        WHEN MATCHED THEN UPDATE SET
          category = source.category,
          amount = source.amount
        WHEN NOT MATCHED AND source.operation = 'insert' THEN INSERT (id, category, amount)
          VALUES (source.id, source.category, source.amount)
    """


def _rows(spark: SparkSession, qualified: str) -> list[dict[str, object]]:
    return [
        {"id": int(row.id), "category": str(row.category), "amount": int(row.amount)}
        for row in spark.sql(f"SELECT id, category, amount FROM {qualified} ORDER BY id").collect()
    ]


def _run(spark: SparkSession, scenarios: tuple[IcebergRowLevelScenario, ...]) -> None:
    for scenario in scenarios:
        _emit(scenario.name, "before")
        spark.sql(scenario.statement).collect()
        _emit(scenario.name, "after")


def _expect_failure(spark: SparkSession, scenario: IcebergRowLevelScenario) -> str:
    _emit(scenario.name, "before")
    try:
        spark.sql(scenario.statement).collect()
    except Exception as error:
        error_name = type(error).__name__
        _emit(scenario.name, "expected-failure", error_type=error_name)
        return error_name
    raise RuntimeError(f"Expected Spark SQL scenario {scenario.name!r} to fail")


def _emit(name: str, phase: str, **fields: str) -> None:
    print(
        "MYSTACK_E2E_SCENARIO="
        + json.dumps({"name": name, "phase": phase, **fields}, sort_keys=True)
    )
