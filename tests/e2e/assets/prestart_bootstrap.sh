#!/usr/bin/env bash
# Amazon EMR bootstrap user: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
set -euo pipefail

bucket=$1
printf 'runtime_user=%s\nprestart_marker=%s\njava_tool_options_present=%s\n' \
  "$(id -un)" \
  "${MYSTACK_PRESTART_E2E_MARKER:-missing}" \
  "$([[ -n ${JAVA_TOOL_OPTIONS:-} ]] && printf true || printf false)" \
  | aws s3 cp - "s3://${bucket}/results/prestart-bootstrap.txt"
