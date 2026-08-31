# Repository Navigation

This guide identifies where to find the implementation, tests, operational
commands, and reproducibility assets.

## Root

| Path | Purpose |
| :--- | :--- |
| `README.md` | Setup, commands, API examples, and local runbook |
| `Makefile` | Install, database, fixture, ingestion, API, frontend, and quality targets |
| `docker-compose.yml` | Dedicated local PostgreSQL 17 service |
| `.gitignore` | Local environments, caches, builds, and generated fixtures |

## Backend

The Python project is under `backend/` and uses uv with the committed
`backend/uv.lock`.

| Path | Purpose |
| :--- | :--- |
| `backend/pyproject.toml` | Dependencies, scripts, pytest, Ruff, and mypy configuration |
| `backend/uv.lock` | Locked Python dependency graph |
| `backend/.env.example` | Backend configuration template |
| `backend/migrations/` | Alembic environment and versioned PostgreSQL migrations |
| `backend/src/ledger_balance/config.py` | Pydantic settings and bounds |
| `backend/src/ledger_balance/domain/` | Decimal arithmetic, value objects, and reference reducer |
| `backend/src/ledger_balance/input/` | CSV readers, validation, and input errors |
| `backend/src/ledger_balance/db/` | asyncpg pool and database lifecycle |
| `backend/src/ledger_balance/ingestion/` | Replacement ingestion, bounded workers, and CLI |
| `backend/src/ledger_balance/api/` | FastAPI routes, repository, contracts, errors, health, and rate limiting |
| `backend/src/ledger_balance/tools/` | Synthetic fixture generator and ingestion benchmark |
| `backend/tests/` | Unit, API, ingestion, input, tool, and opt-in PostgreSQL integration tests |

### Backend entry points

```bash
uv run --project backend --locked ledger-generate-fixtures --help
uv run --project backend --locked ledger-ingest --help
uv run --project backend --locked ledger-serve
uv run --project backend --locked ledger-benchmark-ingest --help
```

## Frontend

The React/TypeScript application is under `frontend/` and uses npm with the
committed `frontend/package-lock.json`.

| Path | Purpose |
| :--- | :--- |
| `frontend/package.json` | Scripts and minimal runtime/dev dependencies |
| `frontend/package-lock.json` | Locked JavaScript dependency graph |
| `frontend/.env.example` | Public Vite configuration template |
| `frontend/src/main.tsx` | React entry point |
| `frontend/src/App.tsx` | Dashboard composition and workflow wiring |
| `frontend/src/api/` | Fetch client, contracts, error normalization, and async state |
| `frontend/src/hooks/useLedgerQueries.ts` | Request lifecycle, aborts, retries, and stale-response guards |
| `frontend/src/components/` | Header, cards, form, selector, feedback, and footer |
| `frontend/src/App.css` | Light-theme dashboard layout and responsive styles |
| `frontend/src/*.test.tsx` | React workflow tests |

Run it with:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

## Test map

- `backend/tests/domain/`: exact arithmetic and independent reference behavior.
- `backend/tests/input/`: headers, dates, decimals, rates, names, and missing
  historical-rate validation.
- `backend/tests/ingestion/`: bounded queue, worker cancellation, cleanup, and
  CLI behavior using fakes.
- `backend/tests/api/`: conversion, repository contracts, route errors, and
  process-local rate limiting.
- `backend/tests/integration/`: real PostgreSQL schema, ingestion, repository,
  and API verification. Enable with `LEDGER_RUN_DB_TESTS=1`.
- `backend/tests/tools/`: fixture and benchmark command behavior.
- `frontend/src/App.test.tsx`: account/total workflows and user-facing states.
- `frontend/src/api/*.test.ts`: transport and async-state behavior.

## Common commands

```bash
make install
make db-up
make migrate
make fixtures
make ingest
make api
make frontend
make check
```

The generated files under `backend/fixtures/generated/` are synthetic and
gitignored. Generate them before running the default ingestion or benchmark
commands in a clean checkout.

## Local-only material

The implementation logs under `code/` and the local roadmap under `plan/` are
workspace materials, not runtime dependencies. They are intentionally excluded
from the repository's tracked submission files.
