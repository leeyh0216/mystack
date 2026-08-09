#!/usr/bin/env bash
# Run the AWS client lab with every AWS CLI request pinned to Mystack's public Proxy.
set -euo pipefail

aws() {
  command aws --endpoint-url "$AWS_ENDPOINT_URL" --no-cli-pager "$@"
}

run() {
  printf '\n$ %s\n' "$*"
  "$@"
}

printf '%s\n' '== 1. Write Parquet data and register the Glue table =='
run python verify.py

printf '%s\n' '== 2. Inspect the data through the AWS CLI =='
run aws glue get-database --name client_lab --query 'Database.Name' --output text
run aws glue get-table --database-name client_lab --name events \
  --query 'Table.{name:Name,partitionKeys:PartitionKeys[*].Name}' --output json
run aws s3 ls s3://mystack-client-lab/events/ --recursive
run aws emr list-clusters --query 'Clusters[].{id:Id,state:Status.State}' --output json

printf '%s\n' '== RESULT: AWS CLI and SDK for pandas completed through the Proxy =='
