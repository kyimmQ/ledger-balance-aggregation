# HTTP API Contract

## General rules

- Base prefix: `/api`.
- Content type: `application/json`.
- Currency query values are trimmed and normalized to uppercase.
- Missing `currency` defaults to `USD`.
- Supported currencies come from the live `currencies` table.
- Monetary values are strings with exactly two fractional digits.
- Response rounding is round-half-even.
- Non-USD valuation uses the requested currency's latest currently persisted rate.
- Different currencies may return different valuation dates.
- At a stable database state, account and total endpoints use the same per-currency valuation-date rule.
- USD bypasses FX conversion and returns `valuationDate: null`.

## Get an account balance

```http
GET /api/accounts/{accountId}/balance?currency={currency}
```

### Parameters

| Parameter | Location | Required | Rules |
| :--- | :--- | :--- | :--- |
| `accountId` | path | yes | Integer from 100 through 999 |
| `currency` | query | no | Supported code; defaults to `USD` |

### Successful USD response

```json
{
  "accountId": 100,
  "name": "acct100",
  "currency": "USD",
  "balance": "96.41",
  "valuationDate": null
}
```

### Successful foreign-currency response

```json
{
  "accountId": 100,
  "name": "acct100",
  "currency": "EUR",
  "balance": "89.00",
  "valuationDate": "2026-06-18"
}
```

For a non-USD request:

```text
balance = stored balance_usd / latest EUR-to-USD rate
```

The exact result is rounded once to two decimal places for the response.

## Get the total balance

```http
GET /api/balances/total?currency={currency}
```

### Parameters

| Parameter | Location | Required | Rules |
| :--- | :--- | :--- | :--- |
| `currency` | query | no | Supported code; defaults to `USD` |

### Successful USD response

```json
{
  "currency": "USD",
  "total": "234525.11",
  "valuationDate": null
}
```

### Successful foreign-currency response

```json
{
  "currency": "GBP",
  "total": "184520.15",
  "valuationDate": "2026-06-17"
}
```

The backend calculates the exact USD total with PostgreSQL `SUM(balance_usd)`, divides once by the latest requested-currency rate, and rounds once for the response.

## Error format

All expected client errors use:

```json
{
  "error": {
    "code": "ACCOUNT_NOT_FOUND",
    "message": "Account 999 was not found"
  }
}
```

Do not include stack traces, SQL, connection strings, or internal exception details.

## Status and error codes

| HTTP status | Error code | Condition |
| :--- | :--- | :--- |
| `400` | `INVALID_ACCOUNT_ID` | Account path value is outside the accepted format/range |
| `400` | `INVALID_CURRENCY` | Currency query value is malformed |
| `400` | `UNSUPPORTED_CURRENCY` | Currency is absent from the current `currencies` table |
| `404` | `ACCOUNT_NOT_FOUND` | A valid account ID has no active balance row |
| `503` | `DATASET_NOT_READY` | Required live tables contain no usable dataset yet |
| `503` | `DATABASE_UNAVAILABLE` | PostgreSQL cannot serve the request |
| `500` | `INTERNAL_ERROR` | Unexpected server failure |

A negative balance is a successful `200` result, not an error.

## Read behavior during ingestion

The API is allowed to serve while ingestion clears and rebuilds the live tables. A request may therefore observe no account, a partial total, or a balance that changes between requests.

Each endpoint should still prefer one SQL statement for its balance/total and latest-rate lookup. This gives that individual request one statement-level PostgreSQL snapshot without adding whole-import publication machinery.

## Optional operational endpoint

The implementation may add:

```http
GET /health
```

This endpoint is operational and does not expand the balance product contract. Account lists, search, pagination, authentication, and mutation endpoints are not part of Phase 0.
