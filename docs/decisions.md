# Architecture and Engineering Decisions

## 1. Backend stack

The ingestion program and HTTP backend will use Python 3.

The read server will use FastAPI. The implementation should use:

- Pydantic models for configuration, request validation, and response contracts;
- Python `Decimal` for authoritative financial arithmetic;
- an asynchronous PostgreSQL driver and bounded connection pool;
- pytest for unit and integration testing; and
- a migration tool rather than schema creation embedded in request handling.

The ingestion command and FastAPI server are separate executable entry points. The ingestion process must close its files and database pool and exit after completing its writes.

## 2. Ingestion replaces the dataset

Each input pair represents a complete replacement dataset. A successful second ingestion does not add the same transactions onto existing balances.

Example:

```text
First completed import: account 100 = 129.50 USD
Same files imported again: account 100 = 129.50 USD
```

The absence of a transaction-level unique ID means the application will not attempt transaction deduplication. It will not treat `(account_id, currency, date)` as a transaction key because multiple valid transactions may share those values.

## 3. Clean and rebuild the live tables directly

The assessment's main database concern is correctness under concurrent transaction updates, not zero-downtime replacement of an old dataset.

Each ingestion run therefore:

1. assumes it is the only ingestion process;
2. clears the live tables in foreign-key-safe order;
3. inserts supported currencies and exchange rates;
4. applies converted USD deltas concurrently and directly to `account_balances` with atomic upserts;
5. waits for all writes to finish; and
6. closes its resources and exits.

The FastAPI server may run at the same time. Its reads reflect whatever rows are committed when each query begins. During ingestion it may return an empty table, a missing account, a partial total, or a progressively changing balance. This behavior is intentional and accepted.

There are no import-run, active-snapshot, staging, publication, rollback, or history tables.

## 4. Failure and retry policy

Ingestion is not resumable.

If parsing, conversion, validation, or persistence fails:

- already committed live rows remain in their partially rebuilt state;
- no rollback to the previous dataset is attempted;
- the process exits with a nonzero status; and
- the user reruns ingestion from the beginning after correcting the failure.

No automatic row-level skip is allowed. Partial committed results are acceptable only as a failure state until the user reruns ingestion.

## 5. Financial precision

### Storage

Use PostgreSQL `NUMERIC(38,18)` for:

- transaction-derived USD deltas when materialized;
- exchange rates; and
- persisted USD account balances.

This provides 20 integer digits and 18 fractional digits. It comfortably preserves the sample rates and gives substantial headroom for aggregation while imposing a clear schema bound. Input outside this range fails instead of silently overflowing or truncating.

### Python arithmetic

- Parse CSV numeric text directly with `Decimal(text)`.
- Never parse through `float`.
- Use a decimal context precision of at least 50 significant digits for multiplication, division, and reference totals.
- Treat all authoritative intermediate values as `Decimal`.
- Reject non-finite values such as `NaN` and infinity.

### Rounding

- Do not round `plus`, `minus`, rates, per-row USD deltas, account accumulation, or database totals during normal processing.
- PostgreSQL stores the final values at the declared 18-digit fractional scale.
- Round only when producing the public API balance or total.
- Quantize responses to `Decimal("0.01")` with `ROUND_HALF_EVEN`.
- Serialize money as a JSON string with exactly two fractional digits, including negative and zero results.

Two fractional digits are an assignment-wide reporting convention, not a claim that every real-world currency has two minor units. Currency-specific minor-unit metadata is outside the supplied input and is not inferred.

### Total calculation

Calculate the exact total in PostgreSQL as `SUM(balance_usd)`, then convert and round once. Do not round each account and sum the rounded presentation values.

## 6. Historical exchange rates

At ingestion, every transaction uses the rate matching its exact `(currency, date)` pair:

```text
usd_delta = (plus - minus) × historical_rate
```

A missing matching historical rate is a fatal ingestion error even though the assignment's happy-path input is expected to provide all required pairs.

## 7. Latest rate is per requested currency

The rate file may contain different latest dates for different currencies. There is no global maximum date that is valid for every currency.

For a non-USD request, query the live table's newest persisted rate for that requested currency:

```sql
ORDER BY rate_date DESC
LIMIT 1
```

Consequences:

- EUR and GBP responses may have different valuation dates.
- The account and total endpoints must return the same valuation date when requested with the same currency against the same committed dataset.
- The selected valuation date is returned in the API response.
- USD requires no exchange rate and returns `valuationDate: null`.

The latest date is derived from persisted `exchange_rates`; it is not duplicated as a mutable column on `currencies`, avoiding inconsistent latest-date metadata.

## 8. Supported currencies

`currencies` is the authoritative set of supported API currency codes in the committed live dataset.

- Ingestion inserts every distinct currency from the rate file and always inserts USD.
- USD still bypasses FX; a USD rate row is not required when the rate file has none, and ingestion does not invent one.
- `exchange_rates` references `currencies` through a foreign key.
- A supported non-USD currency must have at least one persisted positive rate.
- Currency codes are stored uppercase.
- API input may be normalized to uppercase before lookup.
- USD is supported and bypasses rate lookup. It must exist in `currencies` for a consistent supported-currency model.

## 9. Input behavior

The implementation targets the assignment's happy-path data and avoids building a rejected-row subsystem.

Assumptions:

- files are UTF-8 comma-separated CSV with the documented headers;
- dates use `YYYY-MM-DD`;
- account IDs are integers from 100 through 999;
- names are non-empty and consistent for an account ID;
- `plus` and `minus` are non-negative finite decimal strings;
- currencies are valid non-empty codes and are normalized to uppercase;
- `(currency, date)` rate rows are unique;
- rates are positive finite decimal strings; and
- every transaction has a matching historical rate.

The parser still fails fast with file name and row number when a required value cannot be parsed. It does not silently skip bad rows; already committed data may remain until rerun.

## 10. Configuration

Use environment variables for infrastructure configuration and command-line arguments for input paths.

Expected configuration includes:

- `DATABASE_URL`;
- API host and port;
- allowed frontend origin; and
- ingestion concurrency, which must not exceed the database pool maximum.

Phase 4 uses concurrent per-row upserts. Queue capacity is derived from ingestion
concurrency, so there is no database batch-size or queue-size setting.

For local development, backend settings are loaded from `backend/.env`. Public frontend configuration is loaded separately from `frontend/.env.local`; it must contain only browser-safe `VITE_*` values. Tracked templates live beside them as `backend/.env.example` and `frontend/.env.example`.

Do not store secrets in source control.
