# Deliverables and Acceptance

## Required project deliverables

### Documentation

- Architecture and decision record.
- Simple live database model.
- API contract with examples and errors.
- Setup and run instructions.
- Assumptions, precision policy, and failure behavior.
- Measured ingestion performance.

### Backend

- Python project with locked dependencies.
- Versioned PostgreSQL migrations.
- Separate ingestion CLI.
- Separate FastAPI server command.
- Exact decimal domain calculations.
- CSV parsers and happy-path validation.
- Bounded concurrent balance persistence.
- [x] Account and total read services.

### Database

- Normalized currency table.
- Historical exchange-rate table referencing currency.
- One current account balance per account.
- Constraints and indexes supporting required invariants and reads.

### Frontend

- [x] React application.
- [x] Account ID lookup.
- [x] Supported-currency selection.
- [x] Account balance display.
- [x] Total balance display.
- [x] Loading, success, not-found, and error states.
- [x] Zero and negative balance presentation.
- [ ] Empty-dataset UI state has a dedicated frontend workflow test.
- [ ] Responsive and accessible presentation has a full manual browser and
      screen-reader audit.

### Verification

- Unit tests for exact arithmetic and conversion.
- Parser tests.
- PostgreSQL migration and integration tests.
- Concurrency stress tests against a sequential decimal reference.
- [x] API contract tests.
- [x] React component and workflow tests.
- Separate-process restart-isolation test.
- 50,000-row performance measurement.

## Implementation sequence

1. Scaffold Python/FastAPI and React projects.
2. Implement pure decimal arithmetic and parsers.
3. Create migrations for the three live tables.
4. Implement correct sequential ingestion.
5. Add bounded concurrent writes and stress tests.
6. Implement database reads against the progressively updated live tables.
7. Implement the FastAPI contract.
8. Implement the React workflows.
9. Run end-to-end, failure, restart, and performance verification.
10. Complete the submission README and clean-environment rehearsal.

## Acceptance checklist

### Financial correctness

- [ ] Each row uses `(plus - minus) × rate(currency, row date)`.
- [ ] Negative and zero results remain valid.
- [ ] No authoritative calculation uses binary floating point.
- [ ] No transaction is rounded before account aggregation.
- [ ] Stored balances use `NUMERIC(38,18)`.
- [ ] API money is rounded once with round-half-even and returned as a two-decimal string.
- [ ] The exact database total equals the sum of exact stored account balances.

### Exchange rates

- [ ] All historical input rates are persisted.
- [ ] Every rate references a supported currency.
- [ ] Missing historical rates fail ingestion.
- [ ] Non-USD reads use the requested currency's own latest persisted date.
- [ ] USD reads perform no FX conversion.
- [ ] Account and total reads use the same latest-rate rule for a requested currency.

### Ingestion and persistence

- [ ] A successful rerun replaces rather than adds to the previous dataset.
- [x] Concurrent atomic increments lose no updates.
- [x] Work is bounded by a queue, fixed workers, and asyncpg connection pool; no semaphore is used.
- [ ] A run clears live tables before rebuilding them.
- [ ] Empty, partial, and changing API results during ingestion are accepted and documented.
- [ ] A failed run may leave partial data, and rerunning clears and rebuilds it.
- [ ] Ingestion closes resources and exits.

### API

- [x] The FastAPI server starts independently of ingestion.
- [x] Both required endpoints match the documented JSON contract.
- [x] Missing currency defaults to USD.
- [ ] Unsupported currency and unknown account behavior match the contract.
- [x] Each endpoint preferably uses one SQL statement for its own balance/total and rate lookup.
- [x] Database/internal errors do not leak sensitive details.

### Frontend

- [x] Users can choose a currency and look up an account.
- [x] Users can view the total in the same selected currency.
- [x] Valuation dates are visible when conversion occurs.
- [x] Loading, error, not-found, zero, and negative states are clear.
- [x] Stale responses cannot overwrite newer selections.
- [ ] Full responsive browser and screen-reader behavior is manually audited.

### Delivery

- [ ] All migrations, tests, linting, type checks, and builds pass (the
      opt-in PostgreSQL integration suite remains skipped unless explicitly
      enabled).
- [x] Frontend lint, 22 workflow/unit tests, and the production build pass.
- [x] Ingestion of 50,000 rows is measured and documented.
- [ ] Restart isolation is demonstrated after the ingestion process exits.
- [ ] A clean checkout can be run using only documented commands.
- [ ] No secrets, local implementation logs, or machine-specific paths are committed.

### Phase 5 API verification

- [x] The API has no authentication requirement, and process-local rate-limit
  behavior is covered by API contract tests.
- [x] Real PostgreSQL API integration verification is available as an opt-in
  destructive test against the dedicated local Docker `ledger` database.
- [ ] React, a true separate-process restart rehearsal, and final clean-checkout
  delivery remain later gates unless independently evidenced.

## Deferred features

- Resumable ingestion.
- Transaction-level deduplication.
- Rejected-row quarantine.
- Raw transaction audit history.
- Account list/search/pagination.
- Authentication and authorization are not required for this assignment.
- Live FX providers.
- Distributed queues, caches, or microservices.
- Production deployment and observability platforms.
