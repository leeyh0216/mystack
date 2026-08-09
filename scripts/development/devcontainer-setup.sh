#!/usr/bin/env bash
# Lifecycle commands follow the Dev Container specification:
# https://containers.dev/implementors/json_reference/#lifecycle-scripts
# Locked workspace synchronization follows the official uv contract:
# https://docs.astral.sh/uv/concepts/projects/sync/
# Frontend synchronization follows npm ci's lockfile contract:
# https://docs.npmjs.com/cli/v11/commands/npm-ci
set -euo pipefail

uv sync --locked --all-packages
npm ci --ignore-scripts
uv run pre-commit install

printf '%s\n' 'Mystack development environment is ready. Run: make frontend && make up'
