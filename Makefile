# Human-facing command surface. Detailed guide: docs/development.md
CONFIG ?= config/mystack.yaml
SERVICE ?= proxy
MYSTACK_URL ?= http://localhost:4566
MYSTACK_VERSION ?= 0.1.3

.PHONY: help bootstrap sync frontend pre-commit requirements lint format docs antlr-generate antlr-check glue-errors-generate glue-errors-check architecture-check devcontainer-check devcontainer-verify-images ghcr-compose-check model-check coverage-generate coverage-check compatibility-generate compatibility-check compatibility-evidence-generate compatibility-evidence-check compatibility-case registry-check rulesets-check rulesets-apply version-show version-check version-bump package-check test contract up e2e logs down routes threads tasks

help: ## List supported developer commands.
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Validate tools, install locked dependencies, and run fast contracts.
	@./scripts/bootstrap.sh --config "$(CONFIG)"

sync: ## Recreate the Python workspace from uv.lock.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv sync --locked --all-packages

frontend: ## Lint, type-check, test, and build both service-owned UIs.
	@npm run frontend:check

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

antlr-generate: ## Regenerate the pinned Glue partition-expression parser from its G4 grammar.
	@uv run python scripts/generate_glue_expression_parser.py --write

antlr-check: ## Reject ANTLR version, grammar, or committed generated-parser drift.
	@uv run python scripts/generate_glue_expression_parser.py --check

glue-errors-generate: ## Regenerate bilingual evidence from the Glue error-condition catalog.
	@uv run python scripts/glue_error_contracts.py --write

glue-errors-check: ## Reject Glue error coverage, precedence, model, or evidence drift.
	@uv run python scripts/glue_error_contracts.py --check

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

ghcr-compose-check: ## Prove image-only Compose and concise published-image user guidance.
	@uv run python scripts/check_ghcr_compose.py
	@MYSTACK_IMAGE_TAG="$${MYSTACK_IMAGE_TAG:-v0.0.0}" \
	  docker compose -f compose.ghcr.yaml config --quiet

model-check: ## Compare installed botocore with the committed protocol manifest.
	@uv run python scripts/model_manifest.py --check contracts/service-model-manifest.json

coverage-generate: ## Render bilingual API classification matrices from the reviewed baseline.
	@uv run python scripts/api_coverage.py \
	  --write contracts/api-coverage.json \
	  --english docs/compatibility/api-coverage.generated.md \
	  --korean docs/compatibility/api-coverage.ko.generated.md

coverage-check: ## Verify exhaustive API statuses and bilingual generated matrices.
	@uv run python scripts/api_coverage.py \
	  --check contracts/api-coverage.json \
	  --english docs/compatibility/api-coverage.generated.md \
	  --korean docs/compatibility/api-coverage.ko.generated.md

compatibility-generate: ## Compile YAML cases into deterministic CI and bilingual evidence.
	@uv run python scripts/compatibility_matrix.py --write

compatibility-check: ## Reject interoperability manifest, runtime, and generated-output drift.
	@uv run python scripts/compatibility_matrix.py --check

compatibility-evidence-generate: ## Generate CI cases and bilingual evidence from pytest annotations.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv run --all-packages python scripts/compatibility_evidence.py --write

compatibility-evidence-check: ## Reject pytest annotation, operation evidence, and generated-output drift.
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv run --all-packages python scripts/compatibility_evidence.py --check

compatibility-case: ## Run CASE=id from annotated evidence in one bounded, isolated process.
	@test -n "$(CASE)" || (echo "CASE is required; run: make compatibility-case CASE=<id>" >&2; exit 2)
	@MYSTACK_CONFIG_FILE="$(CONFIG)" uv run python scripts/run_compatibility_case.py "$(CASE)"

registry-check: ## Verify GHCR config, OCI index validation, and scanner policy.
	@uv run python scripts/registry_release.py check-config
	@uv run ruff check scripts/registry_release.py tests/test_registry_release.py
	@uv run pytest tests/test_registry_release.py --timeout 60 --timeout-method thread -vv

rulesets-check: ## Validate the file-driven main/develop repository governance policy.
	@uv run python scripts/github_rulesets.py check

rulesets-apply: ## Converge only Mystack-owned rulesets; use REPOSITORY=owner/name DRY_RUN=--dry-run.
	@test -n "$(REPOSITORY)" || (echo "REPOSITORY is required" >&2; exit 2)
	@uv run python scripts/github_rulesets.py apply --repository "$(REPOSITORY)" $(DRY_RUN)

version-show: ## Show the stable version authority; use CHANNEL=snapshot RUN_NUMBER=N SHA=hex.
	@args="--json"; \
	if [ "$(CHANNEL)" = "snapshot" ]; then \
	  test -n "$(RUN_NUMBER)" -a -n "$(SHA)" || \
	    (echo "RUN_NUMBER and SHA are required for CHANNEL=snapshot" >&2; exit 2); \
	  args="--channel snapshot --run-number $(RUN_NUMBER) --sha $(SHA) --json"; \
	fi; \
	uv run python scripts/version.py show $$args

version-check: ## Reject version authority drift; optionally pass BASE_REF and RELEASE_REPOSITORY.
	@args=""; \
	if [ -n "$(BASE_REF)" ]; then args="$$args --base-ref $(BASE_REF)"; fi; \
	if [ -n "$(RELEASE_REPOSITORY)" ]; then \
	  args="$$args --require-unreleased --github-repository $(RELEASE_REPOSITORY)"; \
	fi; \
	uv run python scripts/version.py check $$args

version-bump: ## Update all managed version files; PART=patch|minor|major, VERSION_ARGS=--dry-run.
	@test "$(PART)" = major -o "$(PART)" = minor -o "$(PART)" = patch || \
	  (echo "PART must be major, minor, or patch" >&2; exit 2)
	@uv run python scripts/version.py bump --part "$(PART)" $(VERSION_ARGS)

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
	@curl --fail --silent --show-error "$(MYSTACK_URL)/_mystack/diagnostics/threads" | uv run python -m json.tool

tasks: ## Show asyncio task stacks for the selected management endpoint.
	@curl --fail --silent --show-error "$(MYSTACK_URL)/_mystack/diagnostics/tasks" | uv run python -m json.tool
