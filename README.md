# Ledger Balance Aggregation

A Python/FastAPI, PostgreSQL, and React implementation of the ledger-balance aggregation assessment.

## Status

Phase 1.2 establishes PostgreSQL connectivity, FastAPI health endpoints, and database migrations. Ledger business behavior and React follow in later phases.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose

## Install

```bash
cp .env.example .env
uv sync --project backend --all-groups
```

`backend/uv.lock` is committed. Verify it matches backend project metadata with:

```bash
uv lock --project backend --check
```

## Verify

```bash
make check-backend
```

## PostgreSQL

```bash
make db-up
make migrate
```

## Separate processes

Check database connectivity and exit:

```bash
make ingest
```

Start FastAPI separately:

```bash
make api
```

Foundation endpoints:

```text
GET http://localhost:8000/health/live
GET http://localhost:8000/health/ready
```

## Documentation

- [Architecture decisions](docs/decisions.md)
- [Database model](docs/data-model.md)
- [API contract](docs/api-contract.md)
- [Implementation plan](plan/README.md)
