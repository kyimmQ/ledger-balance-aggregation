# Project Documentation

This folder contains the agreed architecture and contracts for the Ledger Balance Aggregation application.

## Phase 0 decisions at a glance

- Backend and ingestion: Python 3 with FastAPI for the HTTP service.
- Database: PostgreSQL as the durable source of truth.
- Frontend: React.js, implemented in Phase 6 as the presentation layer over the API.
- Ingestion semantics: each run clears the live tables and rebuilds them directly.
- Read visibility: the API may return empty, partial, or progressively updated results while ingestion is running; this is accepted for the assessment.
- Failure: partial live data may remain; the operator fixes the cause and reruns ingestion from the beginning.
- Arithmetic: Python `Decimal` and PostgreSQL `NUMERIC(38,18)`.
- FX at ingestion: each transaction uses its own `(currency, transaction date)` rate.
- FX at read time: each requested currency uses its own latest persisted rate; there is no global valuation date shared by all currencies.
- API money representation: decimal strings rounded once to two fractional digits using round-half-even.
- The API has no authentication requirement for this assignment.
- Product reads have bounded process-local rate limiting, structured errors, and `Cache-Control: no-store` financial responses.
- Input policy: optimize for the assignment's happy path while failing clearly on values that cannot be parsed or matched.

## Documents

1. [Architecture and decisions](decisions.md)
2. [Database model](data-model.md)
3. [HTTP API contract](api-contract.md)
4. [Deliverables and acceptance](delivery.md)
5. [Phase 6 frontend summary](phase-06-summary.md)

The Phase 6 interface is an accessible, responsive light-theme workflow with a
typed browser client. It loads the aggregate balance, looks up an account, and
refreshes both views when the display currency changes. Loading, retry,
not-found, empty, zero, negative, and service-error feedback are presented in
the relevant card; keyboard labels, focus styles, and live-region status
announcements are part of the implementation. The client displays API money
strings and does not perform authoritative financial arithmetic or browser
caching.

The automated frontend gates and a limited desktop/320px dev-page smoke check
are recorded in the Phase 6 summary. A full browser/device and screen-reader
audit, restart-isolation rehearsal, and clean-checkout delivery gate remain
Phase 7 responsibilities.

Gateway/global rate limiting, stable import snapshots, and production deployment
remain out of scope.

## Authoritative formulas

For every transaction:

```text
net_original = plus - minus
usd_delta = net_original × rate(transaction.currency, transaction.date)
```

For an account:

```text
stored_usd_balance = sum(all usd_delta values for that account)
```

For a non-USD read:

```text
requested_balance = stored_usd_balance / latest_persisted_rate(requested_currency)
```

USD reads return the stored USD value without FX conversion.

## Status

These documents freeze Phase 0 decisions and record the completed Phase 5 API
and Phase 6 frontend behavior. Executable implementation must remain consistent
with these contracts unless a decision is intentionally revised and documented.
