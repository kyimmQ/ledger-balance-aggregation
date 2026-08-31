# Phase 6 — Frontend summary

Phase 6 delivers the React/TypeScript presentation layer for the ledger balance
API. The browser renders API-provided money strings and valuation dates; it does
not recalculate authoritative financial values.

## Implementation sections

- **06.1 — UI foundation:** The app shell is composed from a header, total
  balance card, account lookup form, currency selector, account balance card,
  feedback message, and footer. The visual system is a responsive light theme
  with semantic headings, labels, visible focus indicators, and compact cards.
- **06.2 — API client and async state:** The typed client calls the account and
  total endpoints through `/api`, sends `Accept: application/json`, and uses
  `cache: no-store`. Structured API errors are normalized to safe messages.
  Each resource has its own abort controller and monotonically increasing
  request sequence, so superseded currency or account responses cannot replace
  current state.
- **06.3 — Account and total workflows:** USD loads on page start. Users can
  select USD, EUR, or GBP, look up account IDs from 100 through 999, submit
  with Enter or the button, and retry recoverable failures. A currency change
  refreshes the total and the last account lookup. Stored USD, converted
  valuation dates, not-found, dataset-empty, network, and service failures have
  distinct presentation states. Zero and negative values retain their API
  strings and receive explicit context labels.
- **06.4 — UX, accessibility, and performance polish:** Loading and refreshing
  states use `aria-busy` and live status feedback. Inputs and controls have
  semantic labels, keyboard operation, and visible focus treatment. The client
  uses platform `fetch`, avoids financial response caching, and keeps the
  dependency footprint small.
- **06.5 — Verification and delivery:** Documentation and delivery checklists
  were reconciled with the implemented behavior. Automated gates and the
  limits of manual verification are recorded below.

## Evidence

The four implementation commits are:

- `17bab04` — add professional frontend shell (06.1)
- `d0c5a9b` — add typed frontend API client (06.2)
- `50f1210` — connect frontend balance workflows (06.3)
- `b50ead1` — polish frontend states and accessibility (06.4)

Commands run from the repository root:

```text
npm --prefix frontend run lint                 # passed
npm --prefix frontend run test -- --run       # 22 passed, 3 files
npm --prefix frontend run build               # passed
make check                                    # passed
frontend secret/authentication pattern scan       # no matches
git diff --check                              # passed
git status --short --untracked-files=all       # clean before docs changes
```

`make check` also passed the backend lock, format, lint, type, and test gates:
219 backend tests passed, 52 opt-in PostgreSQL integration tests were skipped,
and one existing Starlette/httpx deprecation warning was reported. Its
frontend portion repeated lint, 22 tests, and the production build.

The production bundle contains 28 transformed modules:

| Asset | Raw | Gzip |
| :--- | ---: | ---: |
| `index.html` | 0.41 kB | 0.27 kB |
| `assets/index-C6LXsQJ5.css` | 6.61 kB | 2.20 kB |
| `assets/index-DtmSDeGy.js` | 205.98 kB | 64.35 kB |

The generated `frontend/dist` output is ignored and was not added to the
delivery changes. No API key, authentication header, secret setting, or local
implementation log was added to frontend or documentation files.

## Manual verification limits

With the Vite development server running, Chrome headless loaded the page at
1280×900 and 320×900. Both smoke checks found the dashboard title, total card,
account lookup, currency selector, submit control, and footer in the rendered
DOM. The backend was not started for this smoke check, so the page displayed
the expected safe network-error and retry state.

This is a limited dev-page/DOM smoke check, not a complete visual browser,
device, keyboard, or screen-reader audit. A dedicated empty-dataset workflow
test, separate-process restart rehearsal, clean-checkout rehearsal, and full
manual responsive/accessibility audit remain Phase 7 delivery responsibilities.
