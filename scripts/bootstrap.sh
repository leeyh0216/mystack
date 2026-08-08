#!/usr/bin/env bash
# uv installation: https://docs.astral.sh/uv/getting-started/installation/
# Docker Compose: https://docs.docker.com/compose/install/
set -euo pipefail

config_path="config/mystack.yaml"
while (($#)); do
  case "$1" in
    --config)
      config_path="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

for command_name in uv docker; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done
docker compose version >/dev/null

if [[ ! -f "$config_path" ]]; then
  echo "Configuration file not found: $config_path" >&2
  exit 1
fi

export MYSTACK_CONFIG_FILE="$config_path"
echo "[mystack] syncing locked Python workspace"
uv sync --locked --all-packages
echo "[mystack] checking bilingual documentation and official references"
uv run python scripts/check_docs.py
echo "[mystack] checking the source-free GHCR user Compose file"
make ghcr-compose-check
echo "[mystack] checking hash-locked container requirements"
uv run python scripts/export_requirements.py --check
echo "[mystack] checking pinned AWS service models"
uv run python scripts/model_manifest.py --check contracts/service-model-manifest.json
echo "[mystack] checking manifest-driven interoperability cases"
uv run python scripts/compatibility_matrix.py --check
echo "[mystack] checking exhaustive API classification and generated matrices"
uv run python scripts/api_coverage.py \
  --check contracts/api-coverage.json \
  --english docs/compatibility/api-coverage.generated.md \
  --korean docs/compatibility/api-coverage.ko.generated.md
echo "[mystack] running fast tests with configured timeout"
test_timeout=$(uv run python scripts/config_value.py tests.unit_timeout_seconds)
uv run pytest shared/tests proxy/tests tests/architecture \
  --timeout "$test_timeout" --timeout-method thread

if command -v direnv >/dev/null 2>&1; then
  echo "[mystack] direnv detected; run: direnv allow"
else
  echo "[mystack] direnv is optional: https://direnv.net/"
fi
echo "[mystack] bootstrap complete; next: make up"
