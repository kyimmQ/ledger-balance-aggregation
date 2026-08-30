# Assignment Summary — Ledger Balance Aggregation

## 1. Goal

Build a small full-stack application that:

1. Reads a file containing about 50,000 financial transactions.
2. Reads a file containing daily currency-to-USD exchange rates.
3. Converts every transaction into USD.
4. Calculates the final USD balance for each account.
5. Persists one balance row per account in PostgreSQL.
6. Exits the ingestion process.
7. Starts a separate backend server that reads the persisted data.
8. Exposes an account-balance endpoint and a total-balance endpoint.
9. Returns balances in USD or a requested currency.
10. Provides a React frontend for using both endpoints.

Only synthetic data should be used.

---

## 2. Input Data

### Transactions file

Each row contains:

| Field | Meaning |
| :--- | :--- |
| `id` | Account ID, not a unique transaction ID |
| `name` | Account holder name |
| `plus` | Amount credited |
| `minus` | Amount debited |
| `currency` | Currency of `plus` and `minus` |
| `date` | Date on which the transaction applies |

Important facts:

- The file contains approximately 50,000 rows.
- Account IDs range from `100` to `999`.
- The same account ID appears many times.
- There are at most approximately 900 accounts.
- There are at most 10 distinct transaction dates.

### Exchange-rate file

Each row contains:

| Field | Meaning |
| :--- | :--- |
| `date` | Date on which the rate applies |
| `currency` | Currency being converted |
| `rate` | USD value of one unit of that currency |

The rate direction is:

```text
1 unit of currency × rate = value in USD
```

For example:

```text
1 EUR × 1.0832 = 1.0832 USD
```

The assignment guarantees that every `(currency, date)` pair used by a transaction has a matching exchange rate.

---

## 3. Required Calculations

### Step 1: Calculate a transaction's net amount

```text
net amount = plus - minus
```

Negative net amounts and negative final account balances are valid.

### Step 2: Convert each transaction to USD

Use the rate matching the transaction's own currency and date:

```text
USD transaction amount = (plus - minus) × matching rate
```

Conversion must happen per transaction before aggregation. Transactions cannot first be added in their original currencies because their currencies and dates may differ.

### Step 3: Calculate an account's final USD balance

```text
account balance in USD = sum of all USD transaction amounts for that account
```

In mathematical form:

```text
balanceUSD(account) = Σ ((plus - minus) × rate(currency, transaction date))
```

### Example

Suppose account `100` has these transactions:

| Net amount | Currency | Rate | USD amount |
| :--- | :--- | :--- | :--- |
| `250.00 - 120.50 = 129.50` | USD | `1.0` | `129.50` |
| `15.25 - 60.00 = -44.75` | SGD | `0.7395` | `-33.092625` |

The stored balance is:

```text
129.50 - 33.092625 = 96.407375 USD
```

Keep sufficient decimal precision internally and round only when producing a display value, unless a different rounding policy is explicitly documented.

---

## 4. Read-Time Currency Conversion

All balances are stored in USD. When the API receives a request for another currency, it must use the rate for the **most recent date in the exchange-rate input**.

This is different from ingestion:

- Ingestion uses each transaction's own date.
- API conversion uses one common latest valuation date.

Because rates convert foreign currency to USD, converting USD back to a requested currency requires division:

```text
balance in requested currency = stored USD balance / latest requested-currency rate
```

For example:

```text
Stored balance:       108.32 USD
Latest EUR rate:      1.0832 USD per EUR
Requested balance:    108.32 / 1.0832 = 100 EUR
```

Rules:

- A missing currency parameter defaults to USD.
- A request for USD returns the stored USD balance without conversion.
- The account endpoint and total endpoint must use the same latest valuation date.
- The total is the sum of all stored account balances, converted using that same rate.

---

## 5. Required Architecture

```text
Transactions CSV ─┐
                  ├──> Ingestion program ──> PostgreSQL
Exchange rates ───┘          |
                              └── exits after ingestion

React frontend ──> Separate backend API ──> PostgreSQL
```

The ingestion program and backend server must be separate runs.

The backend must not depend on an in-memory object created by ingestion. After ingestion exits, the database must contain everything needed to preserve account balances. Persisting exchange rates in PostgreSQL is also the safest way to support read-time conversion without depending on the original input files.

---

## 6. PostgreSQL Responsibilities

PostgreSQL must contain exactly one final balance row per account ID.

A reasonable schema is:

```text
account_balances
├── account_id       primary key
├── name
└── balance_usd      exact decimal value
```

Persisting rates is recommended:

```text
exchange_rates
├── rate_date
├── currency
├── usd_rate
└── primary key (rate_date, currency)
```

Use exact decimal types such as PostgreSQL `NUMERIC`, Python `Decimal`, or a decimal library in Node.js. Binary floating-point types can introduce financial rounding errors.

---

## 7. Concurrency Requirement

Transaction writes may overlap and may complete in any order. The result must always be correct, including when several workers update the same account simultaneously.

A naive read-modify-write sequence can lose updates:

```text
Worker A reads 100
Worker B reads 100
Worker A adds 20 and writes 120
Worker B adds 30 and writes 130

Expected result: 150
Stored result:   130
```

The addition should therefore happen atomically inside PostgreSQL. One common approach is:

```sql
INSERT INTO account_balances (account_id, name, balance_usd)
VALUES ($1, $2, $3)
ON CONFLICT (account_id)
DO UPDATE SET
    balance_usd = account_balances.balance_usd
                + EXCLUDED.balance_usd;
```

PostgreSQL serializes conflicting updates to the same account row, preventing lost updates.

Concurrency should be bounded using a connection pool, semaphore, or worker queue. Do not open 50,000 database connections or start 50,000 unrestricted operations at once.

If using multi-row upserts, first combine duplicate account IDs within each batch. PostgreSQL cannot update the same target row more than once in a single `INSERT ... ON CONFLICT` statement.

---

## 8. Required API

The exact paths and JSON shapes are not specified. A reasonable design is:

### Get one account balance

```http
GET /api/accounts/100/balance?currency=EUR
```

Example response:

```json
{
  "accountId": 100,
  "name": "acct100",
  "currency": "EUR",
  "balance": "89.00",
  "valuationDate": "2026-06-18"
}
```

### Get the total balance

```http
GET /api/balances/total?currency=EUR
```

Example response:

```json
{
  "currency": "EUR",
  "total": "123456.78",
  "valuationDate": "2026-06-18"
}
```

Suggested behavior:

| Situation | Response |
| :--- | :--- |
| Valid request | `200 OK` |
| Invalid ID or currency | `400 Bad Request` |
| Valid but unknown account ID | `404 Not Found` |
| Unexpected server/database failure | `500 Internal Server Error` |

Returning monetary values as decimal strings prevents JavaScript from silently changing their precision. The chosen response format should be documented and used consistently.

---

## 9. React Frontend

The frontend must consume both backend operations. A minimal useful interface contains:

- An account ID input.
- A target-currency selector.
- An action to retrieve an account balance.
- A display for the selected account's balance.
- A display for the total balance.
- Loading, success, empty, and error states.
- The valuation date, if returned by the API.

Use `Intl.NumberFormat` for presentation, but do not use frontend floating-point arithmetic for authoritative financial calculations. The backend and database should remain responsible for conversion and aggregation.

---

## 10. Correctness and Testing Checklist

The implementation should verify:

- [ ] A transaction uses the rate for its own currency and date.
- [ ] Credits and debits are calculated as `plus - minus`.
- [ ] Mixed currencies and dates for one account are handled correctly.
- [ ] Negative and zero balances are preserved.
- [ ] Concurrent updates to the same account do not lose data.
- [ ] Exactly one final row exists per account ID.
- [ ] The total equals the sum of all stored account balances.
- [ ] USD or an omitted currency returns the stored USD value.
- [ ] Foreign-currency reads divide by the latest rate.
- [ ] Both endpoints use the same latest valuation date.
- [ ] The API works after the ingestion process has exited.
- [ ] Unknown accounts and unsupported currencies return clear errors.
- [ ] Decimal precision is preserved.
- [ ] Ingestion completes in reasonable time on local PostgreSQL.

A strong concurrency test compares database results after concurrent ingestion with a trusted single-threaded decimal calculation of the same input.

---

## 11. Important Assumptions to Document

The assignment does not specify every implementation detail. The README should state decisions about:

- CSV parsing and validation behavior.
- Decimal precision and output rounding.
- What happens if one account ID has conflicting names.
- API paths and JSON response formats.
- Unknown account and currency behavior.
- Where exchange rates are stored for the API.
- Whether the latest date is treated as one global maximum date.
- What happens when ingestion is run more than once.
- What happens if ingestion fails after partially writing data.

Do not silently ignore invalid rows or missing rates. Fail clearly or record rejected rows according to a documented policy.

---

## 12. Suggested Deliverables

A complete submission should contain:

- PostgreSQL schema or migrations.
- Ingestion command or script.
- Separate backend-server command.
- React frontend.
- Automated tests for calculations, API behavior, and concurrency.
- README with setup and run instructions.
- Environment-variable configuration, such as `DATABASE_URL`.

Docker Compose can make local setup easier, but it is optional unless separately required.

---

## 13. Recommended Implementation Priorities

For a 1–2 hour assessment, prioritize in this order:

1. Correct decimal and exchange-rate calculations.
2. Atomic concurrent database updates.
3. Durable PostgreSQL storage and separate process lifecycle.
4. Correct account and total endpoints.
5. A small functional React interface.
6. Focused tests and clear setup documentation.
7. Optional UI polish or infrastructure improvements.

The strongest solution is small, reproducible, and demonstrably correct rather than heavily overengineered.
