"""Prove sourced pre-start exports reach a real Spark 3.5 child process.

Spark submission reference: https://spark.apache.org/docs/3.5.4/submitting-applications.html
"""

import argparse
import getpass
import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spark = SparkSession.builder.appName("mystack-prestart-e2e").getOrCreate()
    try:
        (
            spark.range(1)
            .withColumn("runtime_user", lit(getpass.getuser()))
            .withColumn("prestart_marker", lit(os.getenv("MYSTACK_PRESTART_E2E_MARKER")))
            .withColumn("java_tool_options_present", lit(bool(os.getenv("JAVA_TOOL_OPTIONS"))))
            .coalesce(1)
            .write.mode("overwrite")
            .json(args.output)
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
