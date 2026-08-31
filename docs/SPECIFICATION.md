# Ledger Balance Aggregation — Specification

## Purpose

This application ingests synthetic transaction and exchange-rate CSV files,
calculates one exact USD balance per account, persists the result in PostgreSQL,
and serves account and total balances through a FastAPI read API. A React
frontend consumes the API and presents both workflows.

The ingestion command and read server are separate processes. PostgreSQL is the
durable source of truth; ingestion memory is never used to serve reads.

## Input files

### Transactions CSV

Required header:

```csv
id,name,plus,minus,currency,date
```

| Field | Meaning |
| :--- | :--- |
| `id` | Account ID, an integer from 100 through 999 |
| `name` | Non-empty account holder name |
| `plus` | Non-negative credited amount in the row currency |
| `minus` | Non-negative debited amount in the row currency |
| `currency` | Uppercase-normalized currency code |
| `date` | Transaction date in canonical `YYYY-MM-DD` form |

The supplied workload contains 50,000 rows, at most about 900 accounts,
and at most 10 transaction dates. Multiple rows may refer to the same account.

### Exchange-rate CSV

Required header:

```csv
date,currency,rate
```

`rate` is the positive multiplier converting one unit of the source currency to
USD. A rate is identified by `(currency, date)`. Rate keys must be unique, and
every transaction key must have a matching historical rate.

## Financial correctness

For every transaction, the authoritative calculation is:

```text
net_original = plus - minus
usd_delta = net_original × rate(transaction.currency, transaction.date)
```

For an account:

```text
stored_usd_balance = sum(all usd_delta values for that account)
```

Negative and zero balances are valid. No overdraft or non-negative rule is
applied. The exact database total is `SUM(balance_usd)` across account rows.

The implementation parses numeric text directly as Python `Decimal`, never via
binary floating point. Intermediate arithmetic uses a 50-digit Decimal context
and values are stored as PostgreSQL `NUMERIC(38,18)` (20 integer digits and 18
fractional digits). Values outside that bound fail validation.

Values are not rounded per row or per account. API output is quantized once to
`0.01` with round-half-even and serialized as a string, including negative and
zero values.

## Ingestion behavior

Each transaction/rate pair is a complete replacement dataset. A new successful
run clears the live tables before rebuilding them; re-running the same files
does not add the balances a second time. The application does not attempt
transaction-level deduplication because the input has no transaction ID.

The process:

1. Parses and validates the complete rate file.
2. Clears `account_balances`, `exchange_rates`, and `currencies` in a
   foreign-key-safe order.
3. Persists supported currencies and all historical rates.
4. Streams transactions through a bounded queue and fixed worker set.
5. Applies each converted delta using an atomic PostgreSQL upsert.
6. Waits for all workers, prints completion statistics, closes resources, and
   exits.

If parsing, conversion, or persistence fails, already committed rows may remain
as a partial rebuild. The command exits non-zero; it does not silently skip bad
rows, roll back to a previous dataset, or resume. The operator corrects the
cause and reruns from the beginning.

The API may run during ingestion. It reads the currently committed live tables,
so responses can be empty, partial, or progressively changing. No whole-import
snapshot is promised.

## Read API

### Supported currencies

```http
GET /api/currencies
```

The response is populated from the `currencies` table, with USD first and the
remaining codes in alphabetical order:

```json
{
  "currencies": ["USD", "EUR", "GBP"]
}
```

### Account balance

```http
GET /api/accounts/{accountId}/balance?currency={currency}
```

`accountId` is required and must be a decimal integer accepted by PostgreSQL's
`INTEGER` type. An ID that is not present in the ingested 100–999 dataset returns
`ACCOUNT_NOT_FOUND`. `currency` is optional and defaults to USD; input is
trimmed and uppercased.

Example:

```json
{
  "accountId": 100,
  "name": "acct100",
  "currency": "EUR",
  "balance": "89.00",
  "valuationDate": "2026-06-24"
}
```

### Total balance

```http
GET /api/balances/total?currency={currency}
```

Example:

```json
{
  "currency": "USD",
  "total": "-97516.97",
  "valuationDate": null
}
```

USD returns the stored USD value and a null valuation date. For a non-USD
request, the exact USD amount is divided by the requested currency's newest
persisted positive rate. The account and total endpoints use the same lookup
rule for a given currency and return its valuation date.

This project intentionally uses each currency's newest persisted rate rather
than requiring one global date shared by all currencies. This handles sparse
rate files where currencies have different final dates; it is an explicit
interpretation of the project's rate-file requirement.

### Error envelope

Errors use this shape and include a request ID:

```json
{
  "error": {
    "code": "ACCOUNT_NOT_FOUND",
    "message": "Account 100 was not found",
    "requestId": "..."
  }
}
```

Important codes include `INVALID_ACCOUNT_ID`, `INVALID_CURRENCY`,
`UNSUPPORTED_CURRENCY`, `ACCOUNT_NOT_FOUND`, `DATASET_NOT_READY`,
`VALUATION_RATE_UNAVAILABLE`, `DATABASE_UNAVAILABLE`, `DATABASE_TIMEOUT`, and
`RATE_LIMITED`. Internal SQL and connection details are not returned.

Responses are JSON and financial reads use `Cache-Control: no-store`. The API
has no authentication requirement for this application. Rate limiting is a
bounded process-local guard, not a distributed security boundary.

## Frontend behavior

The React application provides:

- currency selectors populated by `GET /api/currencies`;
- total-balance display;
- account lookup without a client-side ID-range assumption;
- Enter-key and button submission;
- loading and refreshing states;
- retry actions for recoverable failures;
- empty-dataset, not-found, zero, negative, and service-error states; and
- currency codes shown alongside returned balance values.

The browser displays API-provided money strings and performs no authoritative
financial arithmetic.

## Non-functional requirements

- Concurrent writes must not lose updates regardless of interleaving.
- Final balances must survive ingestion process exit.
- PostgreSQL is the only durable balance source.
- The implementation uses versioned Alembic migrations.
- Dependencies are locked with `backend/uv.lock` and
  `frontend/package-lock.json`.
- All test data is synthetic and generated by the fixture tool.

## Out of scope

Resumable ingestion, transaction deduplication, import history, raw transaction
audit storage, authentication/authorization, live FX providers, distributed
queues, caches, account search/pagination, and production deployment are not
required.
