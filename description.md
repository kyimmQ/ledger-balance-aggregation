# Full-Stack Engineering Assessment — Ledger Balance Aggregation

**Stack:** Python + PostgreSQL + React.js

---

## Summary

Build a small full-stack application that ingests a file of financial transactions, computes the final balance per account in USD, stores the result in PostgreSQL, exposes read endpoints that return balances in a requested currency, and includes a React.js frontend that consumes those endpoints.

Use synthetic data only.

---

## Input

You will be given two files.

### 1. Transactions file — 50,000 rows

| Field      | Type    | Description                               |
| :--------- | :------ | :---------------------------------------- |
| `id`       | integer | 3-digit account id (100–999)              |
| `name`     | string  | Account holder name                       |
| `plus`     | number  | Amount credited, in currency              |
| `minus`    | number  | Amount debited, in currency               |
| `currency` | string  | Currency code of this row (e.g. USD, EUR) |
| `date`     | date    | Date the transaction applies to           |

- At most ~900 distinct ids; each id appears many times.
- At most 10 distinct dates appear across the file.

First rows (header + sample):

```csv
id,name,plus,minus,currency,date
100,acct100,250.00,120.50,USD,2026-06-15
243,acct243,80.00,0.00,EUR,2026-06-16
587,acct587,0.00,45.75,GBP,2026-06-15
912,acct912,1200.00,300.00,JPY,2026-06-17
100,acct100,15.25,60.00,SGD,2026-06-18
```

### 2. Exchange-rate file

One rate per currency per day, provided as input.

| Field      | Type   | Description                                     |
| :--------- | :----- | :---------------------------------------------- |
| `date`     | date   | The day the rate applies to                     |
| `currency` | string | Currency code                                   |
| `rate`     | number | Multiplier to convert 1 unit of currency to USD |

Every `(currency, date)` pair present in the transactions file has a matching rate.

First rows (header + sample):

```csv
date,currency,rate
2026-06-15,USD,1.0
2026-06-15,EUR,1.0832
2026-06-15,GBP,1.2710
2026-06-15,JPY,0.00642
2026-06-15,SGD,0.7395
```

---

## What to build

Ingest the transactions file and persist, in PostgreSQL, the final balance for each account. After ingestion finishes, the ingesting process must be shut down and a separate server started to serve the read endpoints below from PostgreSQL.

Build a **React.js frontend** that consumes the backend endpoints and presents the account balance and total balance functionality. The frontend implementation, structure, UI/UX, and overall presentation are up to you — use this as an opportunity to showcase your best full-stack work.

---

## Read endpoints

A minimal HTTP interface with two reads, both accepting a target currency parameter:

- **Balance for a given id** — the account’s final balance, in the requested currency.
- **Total** — the sum of all account balances, in the requested currency.

---

## Definition of correctness

- The balance of an account is the sum of its credits minus its debits, with each transaction converted to USD using the rate for its own `(currency, date)`.
- Negative balances are valid. This is pure arithmetic — no overdraft or non-negative rules.
- When a read requests a non-USD currency, convert the stored USD value using the rate for the most recent date present in the exchange-rate input. The same valuation date applies to the per-id balance and the total. A request for USD (or no currency) returns the stored USD value.

---

## Requirements

- **Concurrency.** Transactions are applied concurrently: a write for one row may be issued without waiting for the previous one to finish. The persisted balances must be correct regardless of order or interleaving; no updates may be lost.
- **Restart isolation.** Balances must survive the ingesting process exiting. The read server is a separate run and may not rely on any in-memory state from ingestion.
- **Performance.** Ingestion and persistence must complete in a reasonable time on a local PostgreSQL instance.
- **Persistence.** Final balances live in PostgreSQL, one row per id.
