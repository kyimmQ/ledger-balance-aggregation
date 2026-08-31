# HTTP API Contract

The API serves the currently persisted ledger tables. It is intentionally a
small read-only contract for the account and total views.

## General rules

- Base prefix: `/api`.
- Responses use `application/json` and camel-case JSON fields.
- Currency input is trimmed and uppercased, then checked against the live
  `currencies` table. Omitted `currency` defaults to `USD`.
- Account IDs are integer text in the inclusive range 100 through 999.
- Money is returned as a string with exactly two fractional digits, rounded
  once with round-half-even.
- USD returns the stored USD amount and `valuationDate: null`.
- A non-USD read divides the exact stored USD amount by that currency's newest
  persisted rate. Each currency has its own newest rate and date, so dates may
  differ between currencies.
- Each endpoint obtains its amount and requested-currency rate in one SQL
  statement snapshot. This is request-level consistency, not a whole-import
  snapshot.
- Reads may be empty, partial, or changing while ingestion clears and rebuilds
  the live tables. Product responses use `Cache-Control: no-store`.

## Endpoints

### Get an account balance

```http
GET /api/accounts/{accountId}/balance?currency={currency}
```

`accountId` is required. `currency` is optional and defaults to USD.

Example USD response:

```json
{
  "accountId": 100,
  "name": "acct100",
  "currency": "USD",
  "balance": "96.41",
  "valuationDate": null
}
```

Example foreign-currency response:

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
GET /api/balances/total?currency={currency}
```

`currency` is optional and defaults to USD.

Example USD response:

```json
{
  "currency": "USD",
  "total": "234525.11",
  "valuationDate": null
}
```

Example foreign-currency response:

```json
{
  "currency": "GBP",
  "total": "184520.15",
  "valuationDate": "2026-06-17"
}
```

## Authentication and headers

API-key protection is optional. When `API_KEY` is unset, product requests are
allowed. When it is set, clients must send the exact value in the `X-API-Key`
header; query-string keys are not accepted. Health endpoints are public and
exempt. A React bundle cannot keep a shared API key secret, so do not put
`API_KEY` in frontend environment files or browser code.

Every response includes `X-Request-ID`. A valid caller-supplied ID is echoed;
otherwise the server generates one. Requests that reach the product limiter
include process-local fixed-window headers: `X-RateLimit-Limit` and
`X-RateLimit-Remaining`; a rejected request also includes `Retry-After`.
The limiter is local to one application process and is not a distributed/global
limit.

The API enables `GET` and `OPTIONS` for the configured origins (by default,
`http://localhost:5173`) and allows the `Accept`, `Content-Type`, `X-API-Key`,
and `X-Request-ID` request headers. Responses include
`X-Content-Type-Options: nosniff`; API and health responses also include
`Cache-Control: no-store`.

## Errors

Expected errors use this shape, including a request ID:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Route not found",
    "requestId": "6c3e2df8-6f8c-4bd2-a0c0-ef6c4d3db7a0"
  }
}
```

Messages are stable public messages. Responses never include stack traces,
SQL, connection strings, or internal exception details.

| HTTP status | Error code | Condition |
| :--- | :--- | :--- |
| `400` | `INVALID_REQUEST` | Request validation failed |
| `400` | `INVALID_ACCOUNT_ID` | Account ID is not integer text from 100 through 999 |
| `400` | `INVALID_CURRENCY` | Currency is not 3–8 ASCII letters |
| `400` | `UNSUPPORTED_CURRENCY` | Currency is absent from the live `currencies` table |
| `401` | `UNAUTHORIZED` | API key is configured and missing or incorrect |
| `404` | `ACCOUNT_NOT_FOUND` | Valid account ID has no current balance row |
| `404` | `NOT_FOUND` | Route does not exist |
| `405` | `METHOD_NOT_ALLOWED` | Route exists but does not accept this method |
| `429` | `RATE_LIMITED` | Process-local fixed-window limit was exceeded |
| `503` | `DATASET_NOT_READY` | No current balance dataset is available |
| `503` | `VALUATION_RATE_UNAVAILABLE` | Supported non-USD currency has no persisted rate |
| `503` | `DATABASE_UNAVAILABLE` | Database cannot serve the request |
| `504` | `DATABASE_TIMEOUT` | Database query exceeded its timeout |
| `500` | `INTERNAL_ERROR` | Unexpected server failure |

A negative or zero balance is a successful `200` result. `/health/live` and
`/health/ready` are operational endpoints; they are public and exempt from the
API-key and product rate-limit dependencies.
