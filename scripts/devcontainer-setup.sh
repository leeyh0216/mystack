#!/usr/bin/env bash
# Lifecycle commands follow the Dev Container specification:
# https://containers.dev/implementors/json_reference/#lifecycle-scripts
# Locked workspace synchronization follows the official uv contract:
# https://docs.astral.sh/uv/concepts/projects/sync/
set -euo pipefail

uv sync --locked --all-packages
uv run pre-commit install

printf '%s\n' 'Mystack development environment is ready. Run: make up'
