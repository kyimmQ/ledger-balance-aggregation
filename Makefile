UV := uv
UV_PROJECT := --project backend

.PHONY: install install-backend install-frontend lock db-up db-down migrate ingest api frontend test test-backend test-frontend lint format typecheck build check

install: install-backend install-frontend

install-backend:
	$(UV) sync $(UV_PROJECT) --all-groups

install-frontend:
	npm --prefix frontend install

lock:
	$(UV) lock $(UV_PROJECT)

ingest:
	$(UV) run $(UV_PROJECT) --locked ledger-ingest

api:
	$(UV) run $(UV_PROJECT) --locked ledger-serve

frontend:
	npm --prefix frontend run dev

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
