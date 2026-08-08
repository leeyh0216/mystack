/*
 * Real Spark 3.5 Java application used by the EMR JAR E2E contract.
 * Official submission reference:
 * https://spark.apache.org/docs/3.5.4/submitting-applications.html
 */
package mystack.e2e;

import static org.apache.spark.sql.functions.lit;

import org.apache.spark.sql.SparkSession;

public final class SparkS3JarJob {
    private SparkS3JarJob() {}

    public static void main(String[] args) {
        String output = requiredArgument(args, "--output");
        long rowCount = Long.parseLong(requiredArgument(args, "--row-count"));
        SparkSession spark = SparkSession.builder().appName("mystack-emr-jar-e2e").getOrCreate();
        try {
            spark.range(rowCount)
                    .withColumn("spark_version", lit(spark.version()))
                    .coalesce(1)
                    .write()
                    .mode("overwrite")
                    .json(output);
        } finally {
            spark.stop();
        }
    }

    private static String requiredArgument(String[] args, String name) {
        for (int index = 0; index < args.length - 1; index++) {
            if (name.equals(args[index])) {
                return args[index + 1];
            }
        }
        throw new IllegalArgumentException("Missing required argument " + name);
    }
}
