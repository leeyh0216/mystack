# Human-facing command surface. Detailed guide: docs/development.md
CONFIG ?= config/mystack.yaml
SERVICE ?= proxy
MYSTACK_URL ?= http://localhost:4566
MYSTACK_VERSION ?= 0.1.0

.PHONY: help bootstrap sync pre-commit requirements lint format docs architecture-check devcontainer-check devcontainer-verify-images model-check coverage-check registry-check package-check test contract differential up e2e logs down routes threads tasks

help: ## List supported developer commands.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Validate tools, install locked dependencies, and run fast contracts.
	@./scripts/bootstrap.sh --config "$(CONFIG)"

sync: ## Recreate the Python workspace from uv.lock.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv sync --locked --all-packages

pre-commit: ## Install and run repository-local commit quality gates.
	@uv run pre-commit install
	@uv run pre-commit run --all-files

requirements: ## Regenerate hash-locked container requirements from uv.lock.
	@uv run python scripts/export_requirements.py

lint: ## Run source and import-quality checks.
	@uv run ruff check .

format: ## Format source and apply safe lint fixes.
	@uv run ruff check --fix .
	@uv run ruff format .

docs: ## Validate bilingual identity, section order, links, sources, and Korean style.
	@uv run python scripts/check_docs.py

architecture-check: ## Enforce dependency directions, composition roots, and import cycles.
	@uv run python scripts/architecture_contract.py --root .
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.unit_timeout_seconds); \
	uv run pytest tests/architecture/test_dependencies.py \
	  --timeout "$$timeout" --timeout-method thread -vv

devcontainer-check: ## Validate pinned tools, host paths, endpoint, and lifecycle setup.
	@uv run python scripts/check_devcontainer.py
	@bash -n scripts/devcontainer-setup.sh

devcontainer-verify-images: ## Compare Dev Container image tags with locked registry digests.
	@uv run python scripts/check_devcontainer.py --verify-images

model-check: ## Compare installed botocore with the committed protocol manifest.
	@uv run python scripts/model_manifest.py --check contracts/service-model-manifest.json

coverage-check: ## Verify exhaustive API statuses and bilingual generated matrices.
	@uv run python scripts/api_coverage.py \
	  --check contracts/api-coverage.json \
	  --english docs/compatibility/api-coverage.generated.md \
	  --korean docs/compatibility/api-coverage.ko.generated.md

registry-check: ## Verify GHCR config, OCI index validation, and scanner policy.
	@uv run python scripts/registry_release.py check-config
	@uv run ruff check scripts/registry_release.py tests/test_registry_release.py
	@uv run pytest tests/test_registry_release.py --timeout 60 --timeout-method thread -vv

package-check: ## Build and co-install all wheels under the implicit Mystack namespace.
	@uv build --all-packages
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.package_smoke_timeout_seconds); \
	uv run python scripts/check_namespace_packages.py --dist-dir dist --timeout-seconds "$$timeout"

test: ## Run unit, architecture, and protocol tests with configured timeout.
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.unit_timeout_seconds); \
	uv run pytest -m "not e2e" --timeout "$$timeout" --timeout-method thread

contract: ## Run boto3 and wire protocol contracts with configured timeout.
	@timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.contract_timeout_seconds); \
	uv run pytest -m contract --timeout "$$timeout" --timeout-method thread -vv

differential: ## Opt in to read-only normalized real-AWS comparisons.
	@timeout=$$(uv run python -c 'import json; print(json.load(open("contracts/differential-cases.json"))["timeout_seconds"])'); \
	MYSTACK_REAL_AWS_DIFFERENTIAL=1 uv run pytest -m differential \
	  --timeout "$$timeout" --timeout-method thread -vv

up: ## Build and start the Docker stack with the selected YAML config.
	@wait_timeout=$$(MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/config_value.py tests.compose_wait_timeout_seconds); \
	MYSTACK_CONFIG_SOURCE="$(CONFIG)" docker compose up --build --detach --wait --wait-timeout "$$wait_timeout"

e2e: ## Run black-box boto3, AWS SDK for pandas, Spark, Hive, and Iceberg E2E tests.
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
