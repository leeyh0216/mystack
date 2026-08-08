# This file is sourced as trusted root code; exported values reach EMR, bootstrap, and Spark.
# Configure only values appropriate for your local environment and never echo credentials.
# Docker CLI proxy configuration: https://docs.docker.com/engine/cli/proxy/
export HTTPS_PROXY=http://proxy.example.invalid:8080
export HTTP_PROXY=http://proxy.example.invalid:8080
export NO_PROXY=127.0.0.1,localhost,proxy,emr,glue,localstack
export JAVA_TOOL_OPTIONS="-Dhttps.proxyHost=proxy.example.invalid -Dhttps.proxyPort=8080 ${JAVA_TOOL_OPTIONS:-}"
