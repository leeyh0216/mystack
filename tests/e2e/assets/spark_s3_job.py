"""Real Spark 3.5 local-mode S3A write used by the EMR E2E contract.

Spark submission reference: https://spark.apache.org/docs/3.5.4/submitting-applications.html
"""

import argparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--row-count", type=int, required=True)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("mystack-emr-e2e").getOrCreate()
    try:
        (
            spark.range(args.row_count)
            .withColumn("spark_version", lit(spark.version))
            .coalesce(1)
            .write.mode("overwrite")
            .json(args.output)
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
