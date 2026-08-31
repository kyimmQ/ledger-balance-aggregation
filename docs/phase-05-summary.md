# Phase 5 — API summary

Phase 5 delivers the read-only FastAPI balance API on top of the persisted
PostgreSQL ledger. `GET /api/accounts/{accountId}/balance` and
`GET /api/balances/total` default to USD, normalize and validate requested
currencies against the live table, and return exact two-decimal strings using
round-half-even. Non-USD responses use that currency's newest persisted rate;
USD responses return `valuationDate: null`.

Each read uses one SQL statement snapshot for its balance/total and rate. Reads
remain intentionally live during replacement ingestion and can be empty,
partial, or changing between requests. Responses are not cached. Structured
errors include a request ID, security headers are applied, CORS is explicitly
configured, and API-key protection is an optional deployment gate. The fixed
window rate limiter is bounded but process-local.

## Verification

- API unit and contract tests cover conversion, errors, optional API keys,
  request/rate-limit headers, and CORS.
- `backend/tests/integration/test_api.py` is an opt-in test against the
  dedicated local Docker `ledger` database. It ingests the generated baseline,
  closes the ingestion pool, starts separate API lifecycles, checks independent
  USD and EUR values, verifies restart persistence, and checks progressive live
  totals after a committed balance change.
- Run the destructive integration check only after verifying the exact local
  database identity:

  ```bash
  docker compose exec -T db psql -U ledger -d ledger -c \
    "SELECT current_database(), current_user, version();"
  DATABASE_URL=postgresql://ledger:ledger@localhost:5432/ledger \
    LEDGER_RUN_DB_TESTS=1 uv run --project backend --locked pytest \
    -c backend/pyproject.toml backend/tests/integration/test_api.py
  ```

## Limitations

The integration test's TestClient creates a separate application lifecycle,
but not a separate operating-system process; a subprocess restart rehearsal is
still a later delivery gate. Authentication lifecycle management, distributed
limits, gateway/WAF/TLS, caching, and stable whole-import snapshots are out of
scope.
