# Ledger Balance Aggregation

A Python/FastAPI, PostgreSQL, and React implementation of the ledger-balance aggregation assessment.

## Status

Phase 1 establishes the backend and frontend foundations, PostgreSQL connectivity, health checks, database migrations, and repository-wide quality tooling. Ledger calculations, CSV ingestion, balance endpoints, and the product interface begin in Phase 2 and later phases.

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

Check PostgreSQL connectivity and exit:

```bash
make ingest
```

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
