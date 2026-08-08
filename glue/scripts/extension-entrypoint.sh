#!/usr/bin/env bash
# Mounted wheel installation uses the official pip/Python packaging workflow:
# https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
set -euo pipefail

config_path=${MYSTACK_CONFIG_FILE:-/etc/mystack/mystack.yaml}
/opt/mystack/venv/bin/mystack-glue-extension-bootstrap --config "$config_path"
exec /opt/mystack/venv/bin/mystack-glue "$@"
