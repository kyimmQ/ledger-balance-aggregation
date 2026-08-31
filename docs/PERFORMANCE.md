# Ingestion Performance

## Scope and method

The benchmark measures the complete replacement-ingestion lifecycle:

- table reset;
- currency and historical-rate persistence;
- all per-row atomic account upserts;
- worker completion and resource cleanup; and
- final database statistics.

The sequential Decimal oracle calculation and complete stored-row comparison
run outside the timed region. Every result below matched every ordered account
row and the exact total from that independent oracle.

## Environment

Measurements were recorded locally on 31 August 2026 (UTC+07):

- CPU: AMD Ryzen 5 5600H, 6 cores / 12 logical CPUs
- Memory: 7.6 GiB
- OS: Linux x86_64
- Docker Engine: 29.7.2
- Python: 3.12.5
- asyncpg: 0.31.0
- PostgreSQL: 17.11 using `postgres:17-alpine`
- Database pool maximum: 10 connections
- Write strategy: bounded concurrent per-row upserts

These are local measurements, not production capacity guarantees.

## Baseline workload

The baseline fixture contains 50,000 transactions, 900 accounts, and 50 rates.
Its exact total is:

```text
-97516.970386899600000000 USD
```

| Workers | Transactions | Accounts | Rates | Elapsed (s) | Rows/s | Queue | Max connections |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50,000 | 900 | 50 | 40.919 | 1,221.9 | 1 | 1 |
| 2 | 50,000 | 900 | 50 | 19.777 | 2,528.2 | 2 | 2 |
| 5 | 50,000 | 900 | 50 | 11.927 | 4,192.3 | 5 | 5 |
| 10 | 50,000 | 900 | 50 | 9.663 | 5,174.4 | 10 | 10 |

All four runs produced the same exact total and complete account-row result.

## Maximum-contention workload

The hotspot fixture contains 50,000 transactions targeting one account and 50
rates. Its exact total is:

```text
788150.493642082600000000 USD
```

| Workers | Transactions | Accounts | Rates | Elapsed (s) | Rows/s | Queue | Max connections |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50,000 | 1 | 50 | 40.659 | 1,229.7 | 1 | 1 |
| 2 | 50,000 | 1 | 50 | 19.700 | 2,538.1 | 2 | 2 |
| 5 | 50,000 | 1 | 50 | 18.472 | 2,706.8 | 5 | 5 |
| 10 | 50,000 | 1 | 50 | 19.461 | 2,569.3 | 10 | 10 |

The slower hotspot result at 10 workers is expected: PostgreSQL must serialize
updates that conflict on the same account row. The result still exactly matches
the sequential oracle, demonstrating no lost updates.

## Recent end-to-end rehearsal

On 31 August 2026, a separate ingestion process loaded the baseline fixture with
the default 10-worker setting and reported:

```text
transactions=50000
accounts=900
rates=50
total_usd=-97516.970386899600000000
elapsed_seconds=12.102316
rows_per_second=4131.440775
```

The run completed successfully, and two separately started API processes served
the persisted results afterward. This single run is a reproducibility check,
not a replacement for the controlled benchmark table above.

## Interpretation

Ten workers are a reasonable general default because they delivered the best
baseline throughput while respecting the ten-connection pool bound. Five
workers were best for the one-account contention extreme. No batching or
automatic concurrency tuning was added because this project focuses on
correct per-row atomic updates and bounded concurrency.

The normal ingestion CLI now reports elapsed time and rows per second for
successful runs. The dedicated benchmark additionally varies concurrency and
compares every stored row and the exact total against the independent reducer.

## Reproduce

```bash
docker compose up -d db
uv run --project backend --locked alembic \
  -c backend/alembic.ini upgrade head
make fixtures
make benchmark
make benchmark \
  TRANSACTIONS=backend/fixtures/generated/hotspot/transactions.csv \
  RATES=backend/fixtures/generated/hotspot/exchange_rates.csv
```

Each benchmark case clears and replaces the configured ledger tables. Run only
against the dedicated local Docker database. Hardware, Docker resources,
storage, network latency, and PostgreSQL tuning can materially change the
results.
