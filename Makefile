UV := uv
UV_PROJECT := --project backend

.PHONY: install lock ingest api test-backend lint-backend format-backend typecheck-backend check-backend db-up db-down migrate

install:
	$(UV) sync $(UV_PROJECT) --all-groups

lock:
	$(UV) lock $(UV_PROJECT)

ingest:
	$(UV) run $(UV_PROJECT) --locked ledger-ingest

api:
	$(UV) run $(UV_PROJECT) --locked ledger-serve

test-backend:
	$(UV) run $(UV_PROJECT) --locked pytest -c backend/pyproject.toml backend/tests

lint-backend:
	$(UV) run $(UV_PROJECT) --locked ruff check --cache-dir backend/.ruff_cache --config backend/pyproject.toml backend

format-backend:
	$(UV) run $(UV_PROJECT) --locked ruff format --config backend/pyproject.toml backend

typecheck-backend:
	$(UV) run $(UV_PROJECT) --locked mypy --config-file backend/pyproject.toml backend/src backend/tests

check-backend:
	$(UV) lock $(UV_PROJECT) --check
	$(UV) run $(UV_PROJECT) --locked ruff format --config backend/pyproject.toml --check backend
	$(UV) run $(UV_PROJECT) --locked ruff check --cache-dir backend/.ruff_cache --config backend/pyproject.toml backend
	$(UV) run $(UV_PROJECT) --locked mypy --config-file backend/pyproject.toml backend/src backend/tests
	$(UV) run $(UV_PROJECT) --locked pytest -c backend/pyproject.toml backend/tests

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	$(UV) run $(UV_PROJECT) --locked alembic -c backend/alembic.ini upgrade head
