# Ledger Balance Aggregation

A Python/FastAPI, PostgreSQL, and React application for ledger-balance aggregation.

## Status

The backend foundation, exact ledger arithmetic, CSV parsing, PostgreSQL schema,
bounded concurrent replacement ingestion command, FastAPI balance API, and
React product interface are implemented.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 or newer and npm
- GNU Make
- Docker with the Docker Compose v2 plugin, or a compatible PostgreSQL instance

## Setup

Optionally verify that the required local tools are available. Docker Compose
is optional when using a compatible PostgreSQL instance:

```bash
make check-prerequisites
```

Create the backend and frontend environment files, install both projects, and start PostgreSQL:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
make install
make db-up
```

`backend/uv.lock` and `frontend/package-lock.json` are committed for reproducible installs.

## Run the processes

Run each process in its own terminal.

Apply the schema migration, then ingest the generated baseline files:

```bash
make migrate
make ingest
```

To ingest different files:

```bash
make ingest TRANSACTIONS=/path/to/transactions.csv RATES=/path/to/exchange_rates.csv
```

Ingestion validates the complete rate file before changing the database, then clears and replaces the live ledger tables. Transaction rows are streamed through a bounded asyncio worker pipeline. Each worker awaits one atomic per-row PostgreSQL upsert at a time; queue capacity and worker count equal `INGEST_CONCURRENCY`, which may not exceed the pool maximum. If a transaction or database operation fails after the reset, the live tables may contain partial data until the command is rerun.

The first producer or worker failure cancels and awaits the bounded pipeline. Individual additive writes are never retried because a lost response may hide a committed update. Ctrl+C also waits for task cleanup before the pool closes. A failed or interrupted run may leave partial data and must be rerun from reset.

PostgreSQL contention tests compare the complete concurrent result with the sequential decimal oracle, including repeated 50,000-row updates to one account.

## Benchmark ingestion

Run the complete replacement-ingestion benchmark for the baseline or hot-account fixture:

```bash
make benchmark
make benchmark TRANSACTIONS=backend/fixtures/generated/hotspot/transactions.csv \
  RATES=backend/fixtures/generated/hotspot/exchange_rates.csv
```

Each command replaces the configured database contents and verifies every stored
account row and the exact total against the sequential decimal oracle. Local
benchmark details and limitations are printed by the command.

Start the FastAPI server on `http://localhost:8000`:

```bash
make api
```

The implemented read endpoints are:

```text
GET http://localhost:8000/api/accounts/100/balance
GET http://localhost:8000/api/balances/total?currency=EUR
```

The API does not require authentication. The application rate limiter is
bounded and process-local, not a distributed security boundary.
Headers, errors, CORS, and live-read behavior are defined by the backend API
implementation and its tests.

Start the Vite development server on `http://localhost:5173`:

```bash
make frontend
```

The frontend is a responsive light-theme dashboard with a total-balance card,
account lookup, supported-currency selector, valuation-date context, and
distinct loading, refreshing, empty, not-found, zero, negative, and error
states. Account IDs are checked before a request; pressing Enter and selecting
“Look up balance” use the same path. Recoverable failures expose a retry action,
and changing currency refreshes the total and the last account lookup.

The typed client sends `GET` requests to `/api` and uses `cache: no-store` for
financial responses. In development, Vite proxies `/api` and `/health` to the
`VITE_API_BASE_URL` value from `frontend/.env.local` (default:
`http://localhost:8000`). A configured base URL is public browser configuration
and must not contain a secret. Backend settings and secrets are loaded
separately from `backend/.env`; the API does not require authentication. The
frontend renders API-provided money strings and does not
recalculate authoritative financial values in the browser.

## Health checks

```text
GET http://localhost:8000/health/live
GET http://localhost:8000/health/ready
```

`/health/live` reports that the API process is running. `/health/ready` also verifies PostgreSQL connectivity.

## Generate deterministic synthetic data

```bash
make fixtures
make fixtures-catalog
```

`make fixtures` writes the baseline mixed file under `backend/fixtures/generated/baseline/`.
`make fixtures-catalog` also writes contention, arithmetic, FX, and size variants
used by the test suite. Safe to rerun; directories are overwritten and gitignored.

```bash
uv run --project backend --locked ledger-generate-fixtures --help
```

To verify the complete API against real PostgreSQL, start and migrate the
dedicated local Docker database, verify its identity, then opt in to the
destructive integration test:

```bash
make db-up
make migrate
docker compose exec -T db psql -U ledger -d ledger -c \
  "SELECT current_database(), current_user, version();"
DATABASE_URL=postgresql://ledger:ledger@localhost:5432/ledger \
  LEDGER_RUN_DB_TESTS=1 uv run --project backend --locked pytest \
  -c backend/pyproject.toml backend/tests/integration/test_api.py
```

The integration test truncates the configured `ledger` database tables. Run it
only against this dedicated local Docker database, never shared or production
data. API responses are not cached while ingestion changes live balances;
`Cache-Control: no-store` is part of the contract.

## Quality checks

Run all backend and frontend format, lint, type, test, and build gates:

```bash
make check
```

Individual targets include `make test`, `make lint`, `make typecheck`, and `make build`.

## Documentation

- [Specification](docs/SPECIFICATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Repository navigation](docs/REPO_NAVIGATION.md)
- [Performance report](docs/PERFORMANCE.md)

Additional planning material is kept outside the tracked application files.
