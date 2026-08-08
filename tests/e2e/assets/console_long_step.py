"""Long-running Spark application used to verify Console Step tracking and cancellation.

Official submit behavior:
https://spark.apache.org/docs/3.5.4/submitting-applications.html
"""

import argparse
import time

from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep-seconds", type=float, required=True)
    arguments = parser.parse_args()
    spark = SparkSession.builder.appName("mystack-console-cancellation").getOrCreate()
    try:
        print("console-long-step-started", flush=True)
        time.sleep(arguments.sleep_seconds)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
