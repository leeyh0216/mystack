#!/usr/bin/env bash
# EMR bootstrap behavior: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
set -euo pipefail

bucket="$1"
venv=/home/hadoop/mystack-e2e-venv
python3.11 -m venv "$venv"
site_packages=$("$venv/bin/python" -c 'import site; print(site.getsitepackages()[0])')
printf 'VALUE = "installed-by-bootstrap"\n' > "$site_packages/mystack_bootstrap_dependency.py"

runtime_user=$(id -un)
root_user=$(sudo id -un)
printf 'runtime_user=%s\nsudo_user=%s\nvenv=%s\n' \
  "$runtime_user" "$root_user" "$venv" \
  | aws s3 cp - "s3://${bucket}/results/bootstrap-marker.txt"
