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
- Account and total read services.

### Database

- Normalized currency table.
- Historical exchange-rate table referencing currency.
- One current account balance per account.
- Constraints and indexes supporting required invariants and reads.

### Frontend

- React application.
- Account ID lookup.
- Supported-currency selection.
- Account balance display.
- Total balance display.
- Loading, success, not-found, empty, and error states.
- Responsive and accessible presentation.

### Verification

- Unit tests for exact arithmetic and conversion.
- Parser tests.
- PostgreSQL migration and integration tests.
- Concurrency stress tests against a sequential decimal reference.
- API contract tests.
- React component and workflow tests.
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
- [ ] Concurrent atomic increments lose no updates.
- [ ] Work is bounded by a queue/semaphore and connection pool.
- [ ] A run clears live tables before rebuilding them.
- [ ] Empty, partial, and changing API results during ingestion are accepted and documented.
- [ ] A failed run may leave partial data, and rerunning clears and rebuilds it.
- [ ] Ingestion closes resources and exits.

### API

- [ ] The FastAPI server starts independently of ingestion.
- [ ] Both required endpoints match the documented JSON contract.
- [ ] Missing currency defaults to USD.
- [ ] Unsupported currency and unknown account behavior match the contract.
- [ ] Each endpoint preferably uses one SQL statement for its own balance/total and rate lookup.
- [ ] Database/internal errors do not leak sensitive details.

### Frontend

- [ ] Users can choose a currency and look up an account.
- [ ] Users can view the total in the same selected currency.
- [ ] Valuation dates are visible when conversion occurs.
- [ ] Loading, error, not-found, zero, and negative states are clear.
- [ ] Stale responses cannot overwrite newer selections.

### Delivery

- [ ] All migrations, tests, linting, type checks, and builds pass.
- [ ] Ingestion of 50,000 rows is measured and documented.
- [ ] Restart isolation is demonstrated after the ingestion process exits.
- [ ] A clean checkout can be run using only documented commands.
- [ ] No secrets, local implementation logs, or machine-specific paths are committed.

## Deferred features

- Resumable ingestion.
- Transaction-level deduplication.
- Rejected-row quarantine.
- Raw transaction audit history.
- Account list/search/pagination.
- Authentication and authorization.
- Live FX providers.
- Distributed queues, caches, or microservices.
- Production deployment and observability platforms.
