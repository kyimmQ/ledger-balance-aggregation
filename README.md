# Ledger Balance Aggregation

A Python/FastAPI, PostgreSQL, and React implementation of the ledger-balance aggregation assessment.

## Status

Phase 1.1 establishes Python packaging, configuration, entry-point separation, and backend quality tooling. Database connectivity, FastAPI, migrations, and React follow in Phase 1.2 and 1.3.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

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

## Separate process placeholders

```bash
make ingest
make api
```

Their database and serving behavior is added in later phases.

## Documentation

- [Architecture decisions](docs/decisions.md)
- [Database model](docs/data-model.md)
- [API contract](docs/api-contract.md)
- [Implementation plan](plan/README.md)
