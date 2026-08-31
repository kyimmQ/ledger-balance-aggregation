UV := uv
UV_PROJECT := --project backend
TRANSACTIONS ?= backend/fixtures/generated/baseline/transactions.csv
RATES ?= backend/fixtures/generated/baseline/exchange_rates.csv
BENCHMARK_CONCURRENCIES ?= 1 2 5 10

.PHONY: install install-backend install-frontend lock check-prerequisites db-up db-down migrate ingest benchmark api frontend fixtures fixtures-catalog test test-backend test-frontend lint format typecheck build check

install: install-backend install-frontend

install-backend:
	$(UV) sync $(UV_PROJECT) --all-groups

install-frontend:
	npm --prefix frontend install

lock:
	$(UV) lock $(UV_PROJECT)

check-prerequisites:
	@missing=0; \
	for command_name in uv python3 node npm make; do \
		if command -v "$$command_name" >/dev/null 2>&1; then \
			case "$$command_name" in \
				uv) version="$$(uv --version 2>/dev/null)" ;; \
				python3) version="$$(python3 --version 2>&1)" ;; \
				node) version="$$(node --version 2>&1)" ;; \
				npm) version="npm $$(npm --version 2>&1)" ;; \
				make) version="$$(make --version 2>/dev/null | sed -n '1p')" ;; \
			esac; \
			case "$$command_name:$$version" in \
				make:*GNU\ Make*) printf 'Found %-8s %s\n' "$$command_name" "$$version" ;; \
				make:*) printf 'ERROR: GNU Make is required, found: %s\n' "$$version" >&2; missing=1 ;; \
				*) printf 'Found %-8s %s\n' "$$command_name" "$$version" ;; \
			esac; \
		else \
			printf 'ERROR: required command not found: %s\n' "$$command_name" >&2; \
			missing=1; \
		fi; \
	done; \
	if command -v docker >/dev/null 2>&1; then \
		if docker compose version >/dev/null 2>&1; then \
			printf 'Found docker compose %s\n' "$$(docker compose version --short 2>/dev/null || docker compose version 2>/dev/null)"; \
		else \
			printf 'WARNING: Docker Compose v2 is unavailable (optional; use a compatible PostgreSQL instance instead)\n' >&2; \
		fi; \
	else \
		printf 'WARNING: Docker is unavailable, so Docker Compose v2 cannot be checked (optional; use a compatible PostgreSQL instance instead)\n' >&2; \
	fi; \
	if [ "$$missing" -ne 0 ]; then \
		printf 'ERROR: install the missing required tools before continuing.\n' >&2; \
		exit 1; \
	fi

ingest:
	$(UV) run $(UV_PROJECT) --locked ledger-ingest --transactions $(TRANSACTIONS) --rates $(RATES)

benchmark:
	$(UV) run $(UV_PROJECT) --locked ledger-benchmark-ingest \
		--transactions $(TRANSACTIONS) \
		--rates $(RATES) \
		--concurrency $(BENCHMARK_CONCURRENCIES)

api:
	$(UV) run $(UV_PROJECT) --locked ledger-serve

frontend:
	npm --prefix frontend run dev

fixtures:
	$(UV) run $(UV_PROJECT) --locked ledger-generate-fixtures --output-dir backend/fixtures/generated/baseline

GENERATE := $(UV) run $(UV_PROJECT) --locked ledger-generate-fixtures
GEN := backend/fixtures/generated

fixtures-catalog: fixtures
	$(GENERATE) --output-dir $(GEN)/hotspot --rows 50000 --accounts 900 --account-distribution hotspot --hot-account-ratio 1.0
	$(GENERATE) --output-dir $(GEN)/minimal-accounts --rows 50000 --accounts 5
	$(GENERATE) --output-dir $(GEN)/medium-accounts --rows 50000 --accounts 200
	$(GENERATE) --output-dir $(GEN)/one-per-account --rows 900 --accounts 900
	$(GENERATE) --output-dir $(GEN)/pareto --rows 50000 --accounts 900 --account-distribution pareto
	$(GENERATE) --output-dir $(GEN)/clustered --rows 50000 --order by-account
	$(GENERATE) --output-dir $(GEN)/credit-only --entry-mode credit-only --rows 2000
	$(GENERATE) --output-dir $(GEN)/debit-only --entry-mode debit-only --rows 2000
	$(GENERATE) --output-dir $(GEN)/dual-entry --dual-entry-ratio 1 --rows 2000
	$(GENERATE) --output-dir $(GEN)/zero-delta --zero-delta-ratio 1 --rows 2000
	$(GENERATE) --output-dir $(GEN)/cancel-pairs --entry-mode cancel-pairs --rows 2000
	$(GENERATE) --output-dir $(GEN)/magnitudes --min-amount 0.01 --max-amount 999999999.99 --rows 2000
	$(GENERATE) --output-dir $(GEN)/float-traps --trap-amount-ratio 1 --currencies USD,SGD --rows 2000
	$(GENERATE) --output-dir $(GEN)/usd-only --currencies USD --rows 2000
	$(GENERATE) --output-dir $(GEN)/eur-only --currencies EUR --rows 2000
	$(GENERATE) --output-dir $(GEN)/single-account-fx --accounts 1 --rows 2000
	$(GENERATE) --output-dir $(GEN)/single-date --dates 1 --rows 2000
	$(GENERATE) --output-dir $(GEN)/micro --rows 10 --accounts 10
	$(GENERATE) --output-dir $(GEN)/empty --rows 0 --accounts 1

test: test-backend test-frontend

test-backend:
	$(UV) run $(UV_PROJECT) --locked pytest -c backend/pyproject.toml backend/tests

test-frontend:
	npm --prefix frontend run test

lint:
	$(UV) run $(UV_PROJECT) --locked ruff check --cache-dir backend/.ruff_cache --config backend/pyproject.toml backend
	npm --prefix frontend run lint

format:
	$(UV) run $(UV_PROJECT) --locked ruff format --config backend/pyproject.toml backend

typecheck:
	$(UV) run $(UV_PROJECT) --locked mypy --config-file backend/pyproject.toml backend/src backend/tests
	npm --prefix frontend run build

build:
	npm --prefix frontend run build

check:
	$(UV) lock $(UV_PROJECT) --check
	$(UV) run $(UV_PROJECT) --locked ruff format --config backend/pyproject.toml --check backend
	$(UV) run $(UV_PROJECT) --locked ruff check --cache-dir backend/.ruff_cache --config backend/pyproject.toml backend
	$(UV) run $(UV_PROJECT) --locked mypy --config-file backend/pyproject.toml backend/src backend/tests
	$(UV) run $(UV_PROJECT) --locked pytest -c backend/pyproject.toml backend/tests
	npm --prefix frontend run lint
	npm --prefix frontend run test
	npm --prefix frontend run build

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	$(UV) run $(UV_PROJECT) --locked alembic -c backend/alembic.ini upgrade head
