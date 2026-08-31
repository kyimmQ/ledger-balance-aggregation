# Ledger Balance Aggregation

A Python/FastAPI, PostgreSQL, and React implementation of the ledger-balance aggregation assessment.

## Status

The backend foundation, exact ledger arithmetic, CSV parsing, PostgreSQL schema, and sequential replacement ingestion command are implemented. Concurrent ingestion, balance endpoints, and the product interface follow in later phases.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 or newer and npm
- Docker with Docker Compose, or a compatible PostgreSQL instance

## Setup

Create the backend and frontend environment files, install both projects, start PostgreSQL, and apply migrations:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
make install
make db-up
make migrate
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

Ingestion validates the complete rate file before changing the database, then clears and replaces the live ledger tables. Transaction rows are streamed and committed one at a time. If a transaction or database operation fails after the reset, the live tables may contain partial data until the command is rerun. The command deliberately performs sequential writes; concurrent performance is added in Phase 4.

Start the FastAPI server on `http://localhost:8000`:

```bash
make api
```

Start the Vite development server on `http://localhost:5173`:

```bash
make frontend
```

The frontend development proxy reads `VITE_API_BASE_URL` from `frontend/.env.local` and defaults to `http://localhost:8000`. Backend settings and secrets are loaded separately from `backend/.env`.

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

`make fixtures` writes the assignment-sized mixed file under `backend/fixtures/generated/baseline/`. `make fixtures-catalog` also writes the contention, arithmetic, FX, and size variants used in later tests. Safe to rerun; directories are overwritten and gitignored.

```bash
uv run --project backend --locked ledger-generate-fixtures --help
```

## Quality checks

Run all backend and frontend format, lint, type, test, and build gates:

```bash
make check
```

Individual targets include `make test`, `make lint`, `make typecheck`, and `make build`.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture decisions](docs/decisions.md)
- [Database model](docs/data-model.md)
- [API contract](docs/api-contract.md)
- [Implementation plan](plan/README.md)
