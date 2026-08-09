#!/usr/bin/env bash
set -euo pipefail

bucket=mystack-spark-client-lab
/opt/mystack/venv/bin/python - <<'PY'
import boto3

s3 = boto3.client("s3", endpoint_url="http://localstack:4566")
try:
    s3.create_bucket(Bucket="mystack-spark-client-lab")
except s3.exceptions.BucketAlreadyOwnedByYou:
    pass
PY

exec /opt/mystack/bin/spark-submit "$@"
