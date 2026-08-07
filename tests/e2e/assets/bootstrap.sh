#!/usr/bin/env bash
# EMR bootstrap behavior: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
set -euo pipefail

bucket="$1"
printf 'bootstrap-completed\n' | aws s3 cp - "s3://${bucket}/results/bootstrap-marker.txt"
