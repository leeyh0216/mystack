# Human-facing command surface. Detailed guide: docs/development.md
CONFIG ?= config/mystack.yaml
SERVICE ?= proxy
MYSTACK_URL ?= http://localhost:4566

.PHONY: help bootstrap sync lint format docs model-check test contract up e2e logs down routes threads tasks

help: ## List supported developer commands.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Validate tools, install locked dependencies, and run fast contracts.
	@./scripts/bootstrap.sh --config "$(CONFIG)"

sync: ## Recreate the Python workspace from uv.lock.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv sync --locked --all-packages

lint: ## Run source and import-quality checks.
	@uv run ruff check .

format: ## Format source and apply safe lint fixes.
	@uv run ruff check --fix .
	@uv run ruff format .

docs: ## Validate bilingual pairs, backlinks, and official references.
	@uv run python scripts/check_docs.py

model-check: ## Compare installed botocore with the committed protocol manifest.
	@uv run python scripts/model_manifest.py --check contracts/service-model-manifest.json

test: ## Run unit, architecture, and protocol tests with configured timeout.
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.unit_timeout_seconds); \
	uv run pytest -m "not e2e" --timeout "$$timeout" --timeout-method thread

contract: ## Run boto3 and wire protocol contracts with configured timeout.
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.contract_timeout_seconds); \
	uv run pytest -m contract --timeout "$$timeout" --timeout-method thread -vv

up: ## Build and start the Docker stack with the selected YAML config.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" docker compose up --build --detach --wait --wait-timeout 300

e2e: ## Run black-box boto3, Spark, Hive, and Iceberg E2E tests.
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.e2e_timeout_seconds); \
	uv run pytest tests/e2e -m e2e --timeout "$$timeout" --timeout-method thread -vv

logs: ## Follow structured logs for all containers or SERVICE=name.
	@docker compose logs --follow "$(SERVICE)"

down: ## Stop containers and remove ephemeral volumes.
	@docker compose down --volumes --remove-orphans

routes: ## Show the active Proxy route registry.
	@curl --fail --silent --show-error "$(MYSTACK_URL)/_mystack/routes" | uv run python -m json.tool

threads: ## Show thread stacks for the selected management endpoint.
	@if [ -n "$${MYSTACK_MANAGEMENT_TOKEN:-}" ]; then \
	  curl --fail --silent --show-error -H "Authorization: Bearer $$MYSTACK_MANAGEMENT_TOKEN" "$(MYSTACK_URL)/_mystack/diagnostics/threads"; \
	else \
	  curl --fail --silent --show-error "$(MYSTACK_URL)/_mystack/diagnostics/threads"; \
	fi | uv run python -m json.tool

tasks: ## Show asyncio task stacks for the selected management endpoint.
	@if [ -n "$${MYSTACK_MANAGEMENT_TOKEN:-}" ]; then \
	  curl --fail --silent --show-error -H "Authorization: Bearer $$MYSTACK_MANAGEMENT_TOKEN" "$(MYSTACK_URL)/_mystack/diagnostics/tasks"; \
	else \
	  curl --fail --silent --show-error "$(MYSTACK_URL)/_mystack/diagnostics/tasks"; \
	fi | uv run python -m json.tool
